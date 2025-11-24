import mysql.connector
from mysql.connector import Error
import hashlib


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "dify_chat"
}

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()
        self._ensure_tables_exist()

    def _connect(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor(dictionary=True)
            print("✅ 数据库连接成功")
        except Error as e:
            print(f"❌ 数据库连接失败: {e}")
            self._create_database()

    def _create_database(self):
        try:
            temp_config = DB_CONFIG.copy()
            temp_config.pop('database')
            temp_conn = mysql.connector.connect(**temp_config)
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            temp_cursor.close()
            temp_conn.close()
            print(f"✅ 数据库 {DB_CONFIG['database']} 创建成功")
            self._connect()
        except Error as e:
            print(f"❌ 创建数据库失败: {e}")
            raise

    def _ensure_tables_exist(self):
        try:
            self.cursor.execute("SHOW TABLES LIKE 'users'")
            if not self.cursor.fetchone():
                self._create_tables()
        except Exception as e:
            print(f"检查表存在性失败: {e}")
            self._create_tables()

    def _create_tables(self):
        try:
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                account VARCHAR(20) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_admin INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                query TEXT,
                response TEXT NOT NULL,
                file_path TEXT,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            self._init_admin()
            self.conn.commit()
            print("✅ 表结构创建成功")
        except Exception as e:
            print(f"❌ 创建表失败: {e}")
            raise

    def _init_admin(self):
        admin_account = "admin"
        admin_password = "123456"
        pwd_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        # 如果存在则更新密码，否则插入
        self.cursor.execute('SELECT id FROM users WHERE account = %s', (admin_account,))
        if self.cursor.fetchone():
            self.cursor.execute('UPDATE users SET password_hash = %s, is_admin = 1 WHERE account = %s',
                                (pwd_hash, admin_account))
        else:
            self.cursor.execute('INSERT INTO users (account, password_hash, is_admin) VALUES (%s, %s, 1)',
                                (admin_account, pwd_hash))
        self.conn.commit()
        print(f"✅ 管理员账号已设置为: {admin_account} / 密码: {admin_password}")

    def register_user(self, account, password):
        if not account.isdigit() or len(account) >= 20:
            return False, "账号必须是纯数字且长度<20位"
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        try:
            self.cursor.execute('INSERT IGNORE INTO users (account, password_hash, is_admin) VALUES (%s, %s, 0)',
                                (account, pwd_hash))
            self.conn.commit()
            return self.cursor.rowcount > 0, "注册成功" if self.cursor.rowcount > 0 else "账号已存在"
        except Exception as e:
            return False, f"注册失败: {str(e)}"

    def login_user(self, account, password):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute('SELECT id, account, is_admin FROM users WHERE account = %s AND password_hash = %s',
                            (account, pwd_hash))
        return self.cursor.fetchone()

    def save_chat(self, user_id, query, response, file_path=""):
        try:
            self.cursor.execute('INSERT INTO chat_records (user_id, query, response, file_path) VALUES (%s, %s, %s, %s)',
                                (user_id, query, response, file_path))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ 保存对话失败: {e}")
            return False

    def get_chat_history(self, user_id):
        self.cursor.execute('SELECT id, create_time, query, response, file_path FROM chat_records WHERE user_id = %s ORDER BY create_time DESC',
                            (user_id,))
        return self.cursor.fetchall()

    def get_all_users(self):
        self.cursor.execute('SELECT id, account, is_admin, created_at FROM users ORDER BY created_at DESC')
        return self.cursor.fetchall()

    def delete_user(self, user_id):
        try:
            self.cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"❌ 删除用户失败: {e}")
            return False

    def delete_user_chat(self, user_id):
        try:
            self.cursor.execute("DELETE FROM chat_records WHERE user_id = %s", (user_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"❌ 删除对话记录失败: {e}")
            return False

    def get_user_stats(self):
        self.cursor.execute('SELECT COUNT(*) as total_users FROM users')
        total_users = self.cursor.fetchone()['total_users']

        self.cursor.execute('SELECT COUNT(*) as total_chats FROM chat_records')
        total_chats = self.cursor.fetchone()['total_chats']

        self.cursor.execute('''
        SELECT account, COUNT(chat_records.id) as chat_count 
        FROM users 
        LEFT JOIN chat_records ON users.id = chat_records.user_id 
        GROUP BY users.id 
        ORDER BY chat_count DESC
        ''')
        user_stats = self.cursor.fetchall()

        return {
            'total_users': total_users,
            'total_chats': total_chats,
            'user_stats': user_stats
        }

