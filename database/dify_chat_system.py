import requests
import os
import hashlib
import mysql.connector
from datetime import datetime
from mysql.connector import Error
import time

# 跳过SSL验证配置
requests.packages.urllib3.disable_warnings()

# === 配置 ===
API_KEY = "app-ThkEAGZSicYWuSGc7ATBEDPw"  # 替换为你的Dify密钥
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",  # 你的MySQL密码
    "database": "dify_chat"
}

# 网络配置
TIMEOUT = 60
RETRY_COUNT = 3
RETRY_DELAY = 3
VERIFY_SSL = False

# 默认管理员账号
ADMIN_ACCOUNT = "666"
ADMIN_PASSWORD = "admin"


# === 数据库操作类 ===
class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
        self._init_admin()

    def _connect(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor(dictionary=True)
            print("✅ 数据库连接成功")
        except Error as e:
            print(f"❌ 数据库连接失败: {e}")
            raise

    def _create_tables(self):
        # 正确删除旧表（修复语法错误）
        self.cursor.execute("DROP TABLE IF EXISTS chat_records;")
        self.cursor.execute("DROP TABLE IF EXISTS users;")  # 修正此处的语法错误
        print("ℹ️ 清理旧表，创建新结构...")

        # 创建用户表
        self.cursor.execute('''
        CREATE TABLE users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            account VARCHAR(20) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_admin INT DEFAULT 0,  # 1为管理员，0为普通用户
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')

        # 创建聊天记录表
        self.cursor.execute('''
        CREATE TABLE chat_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            query TEXT,  # 可存储null（文件上传时）
            response TEXT NOT NULL,
            file_path TEXT,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        self.conn.commit()
        print("✅ 表结构创建成功")

    def _init_admin(self):
        """创建默认管理员账号666"""
        if not self.login_user(ADMIN_ACCOUNT, ADMIN_PASSWORD):
            pwd_hash = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
            self.cursor.execute('''
            INSERT INTO users (account, password_hash, is_admin)
            VALUES (%s, %s, 1)  # 1表示管理员
            ''', (ADMIN_ACCOUNT, pwd_hash))
            self.conn.commit()
            print(f"✅ 已创建默认管理员账号: {ADMIN_ACCOUNT} / 密码: {ADMIN_PASSWORD}")

    def register_user(self, account, password):
        if not account.isdigit() or len(account) >= 20:
            return False, "账号必须是纯数字且长度<20位"
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute('''
        INSERT IGNORE INTO users (account, password_hash, is_admin)
        VALUES (%s, %s, 0)  # 0表示普通用户
        ''', (account, pwd_hash))
        self.conn.commit()
        return self.cursor.rowcount > 0, "注册成功" if self.cursor.rowcount > 0 else "账号已存在"

    def login_user(self, account, password):
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute('''
        SELECT id, is_admin FROM users
        WHERE account = %s AND password_hash = %s
        ''', (account, pwd_hash))
        return self.cursor.fetchone()  # 返回用户ID和是否为管理员

    def save_chat(self, user_id, query, response, file_path=""):
        try:
            self.cursor.execute('''
            INSERT INTO chat_records (user_id, query, response, file_path)
            VALUES (%s, %s, %s, %s)
            ''', (user_id, query, response, file_path))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ 保存对话失败: {e}")
            return False

    def get_chat_history(self, user_id):
        self.cursor.execute('''
        SELECT create_time, query, response, file_path
        FROM chat_records
        WHERE user_id = %s
        ORDER BY create_time DESC
        ''', (user_id,))
        return self.cursor.fetchall()

    # 管理员功能
    def get_all_users(self):
        self.cursor.execute('''
        SELECT id, account, is_admin, created_at 
        FROM users 
        ORDER BY created_at DESC
        ''')
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

    def close(self):
        if self.conn and self.conn.is_connected():
            self.cursor.close()
            self.conn.close()


# === Dify交互类 ===
class DifyClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.conversation_id = None  # 保留对话上下文

    def upload_file(self, file_path):
        if not os.path.exists(file_path):
            return None, None, "文件路径错误（文件不存在）"  # 明确提示路径错误

        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {'.txt': 'text/plain', '.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg'}
        mime_type = mime_map.get(ext, 'application/octet-stream')
        file_type = "image" if mime_type.startswith('image/') else "document"

        for retry in range(RETRY_COUNT + 1):
            try:
                with open(file_path, 'rb') as f:
                    files = {'file': (file_name, f, mime_type)}
                    data = {'user': 'user1', 'purpose': 'chat'}
                    headers = {'Authorization': f'Bearer {self.api_key}'}
                    response = requests.post(
                        FILE_UPLOAD_ENDPOINT,
                        files=files,
                        data=data,
                        headers=headers,
                        timeout=TIMEOUT,
                        verify=VERIFY_SSL
                    )

                if response.status_code == 201:
                    return response.json()['id'], file_type, None
                elif retry < RETRY_COUNT:
                    print(f"⚠️ 上传失败，重试({retry + 1}/{RETRY_COUNT})...")
                    time.sleep(RETRY_DELAY)
                else:
                    return None, None, f"文件路径正确但上传失败 [{response.status_code}]"
            except Exception as e:
                if retry < RETRY_COUNT:
                    print(f"⚠️ 上传错误，重试({retry + 1}/{RETRY_COUNT})...")
                    time.sleep(RETRY_DELAY)
                else:
                    return None, None, f"文件路径错误或读取失败: {str(e)}"
        return None, None, "达到最大重试次数"

    def chat(self, message, file_id=None, file_type=None):
        payload = {
            "query": message,
            "inputs": {},
            "response_mode": "blocking",
            "user": "user1",
            "conversation_id": self.conversation_id
        }
        if file_id and file_type:
            payload["files"] = [{"type": file_type, "transfer_method": "local_file", "id": file_id}]

        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

        for retry in range(RETRY_COUNT + 1):
            try:
                response = requests.post(
                    CHAT_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=TIMEOUT,
                    verify=VERIFY_SSL
                )

                if response.status_code == 200:
                    result = response.json()
                    self.conversation_id = result.get('conversation_id', self.conversation_id)
                    return result.get('answer', '无回复')
                elif retry < RETRY_COUNT:
                    print(f"⚠️ 对话失败，重试({retry + 1}/{RETRY_COUNT})...")
                    time.sleep(RETRY_DELAY)
                else:
                    return f"对话失败 [{response.status_code}]: {response.text[:200]}"
            except Exception as e:
                if retry < RETRY_COUNT:
                    print(f"⚠️ 对话错误，重试({retry + 1}/{RETRY_COUNT})...")
                    time.sleep(RETRY_DELAY)
                else:
                    return f"对话错误: {str(e)}"
        return "达到最大重试次数"


# === 主程序 ===
def main():
    try:
        db = Database()
    except:
        print("数据库初始化失败，程序退出")
        return

    # 程序主循环
    while True:
        print("\n===== 系统入口 =====")
        print("1. 登录")
        print("2. 注册")
        print("3. 退出程序")
        choice = input("请选择: ").strip()

        if choice == "3":
            print("👋 退出程序，再见！")
            db.close()
            return

        user = None
        if choice == "1":
            account = input("账号（纯数字）: ").strip()
            password = input("密码: ").strip()
            user = db.login_user(account, password)
            if not user:
                print("❌ 账号或密码错误")
                continue
            print(f"✅ 登录成功！用户ID: {user['id']} {'(管理员)' if user['is_admin'] else ''}")

        elif choice == "2":
            account = input("设置账号（纯数字，长度<20）: ").strip()
            password = input("设置密码: ").strip()
            success, msg = db.register_user(account, password)
            if success:
                print(f"✅ {msg}，请登录")
                user = db.login_user(account, password)
                print(f"✅ 登录成功！用户ID: {user['id']}")
            else:
                print(f"❌ {msg}")
                continue

        else:
            print("❌ 无效选择")
            continue

        # 初始化Dify客户端
        dify = DifyClient(API_KEY)
        user_id = user['id']
        is_admin = user['is_admin']

        # 功能菜单循环
        while True:
            print("\n===== 功能菜单 =====")
            print("1. 查看历史记录")
            print("2. 进入持续对话（输入3退出对话模式）")
            if is_admin:
                print("3. 管理员功能")
            print(f"{'4' if is_admin else '3'}. 退出当前用户")

            cmd = input("请选择: ").strip()

            if cmd == "1":
                # 查看历史记录
                print("\n===== 历史记录 =====")
                history = db.get_chat_history(user_id)
                if not history:
                    print("暂无历史记录")
                    continue
                for i, record in enumerate(history, 1):
                    print(f"\n[{i}] 时间: {record['create_time']}")
                    print(f"文件: {record['file_path'] or '无'}")
                    print(f"你: {record['query'] if record['query'] is not None else 'null'}")  # 文件上传时显示null
                    print(f"回复: {record['response']}")

            elif cmd == "2":
                # 持续对话模式（唯一消息入口）
                print("\n===== 持续对话模式 =====")
                print("提示：输入消息即可发送，输入'file:文件路径'上传文件，输入3退出此模式")
                while True:
                    user_input = input("你: ").strip()
                    if user_input == "3":
                        print("🔙 退出持续对话模式，返回功能菜单")
                        break

                    file_path = ""
                    file_id = None
                    file_type = None
                    user_query = user_input  # 默认为用户输入
                    is_file_upload = user_input.startswith("file:")

                    if is_file_upload:
                        file_path = user_input[5:].strip().replace("\\", "/")
                        print(f"正在上传文件: {file_path}...")
                        file_id, file_type, error = dify.upload_file(file_path)
                        if error:
                            print(f"❌ {error}（不记录此操作）")  # 错误不记录
                            continue
                        user_query = None  # 文件上传成功时query为null
                        user_input = "请分析这个文件的内容"

                    # 获取回复
                    print("正在获取回复...")
                    reply = dify.chat(user_input, file_id, file_type)
                    print(f"🤖 回复: {reply}")

                    # 保存对话
                    if db.save_chat(user_id, user_query, reply, file_path):
                        print("✅ 对话已保存")
                    else:
                        print("⚠️ 对话保存失败")

            elif cmd == "3" and is_admin:
                # 管理员功能
                while True:
                    print("\n===== 管理员功能 =====")
                    print("1. 查看所有用户")
                    print("2. 删除指定用户")
                    print("3. 清空用户对话记录")
                    print("4. 返回上一级")
                    admin_cmd = input("请选择: ").strip()

                    if admin_cmd == "1":
                        users = db.get_all_users()
                        if not users:
                            print("暂无用户")
                            continue
                        print("\nID  | 账号 | 角色 | 创建时间")
                        for u in users:
                            role = "管理员" if u['is_admin'] else "普通用户"
                            print(f"{u['id']:<4} | {u['account']:<4} | {role} | {u['created_at']}")

                    elif admin_cmd == "2":
                        target_id = input("输入要删除的用户ID: ").strip()
                        if not target_id.isdigit():
                            print("❌ 用户ID必须是数字")
                            continue
                        if int(target_id) == user_id:
                            print("❌ 不能删除当前登录账号")
                            continue
                        if db.delete_user(target_id):
                            print(f"✅ 已删除用户ID {target_id}")
                        else:
                            print(f"❌ 用户ID {target_id} 不存在")

                    elif admin_cmd == "3":
                        target_id = input("输入要清空对话的用户ID: ").strip()
                        if not target_id.isdigit():
                            print("❌ 用户ID必须是数字")
                            continue
                        if db.delete_user_chat(target_id):
                            print(f"✅ 已清空用户ID {target_id} 的对话")
                        else:
                            print(f"❌ 操作失败")

                    elif admin_cmd == "4":
                        break

                    else:
                        print("❌ 无效选择")

            elif cmd == ("4" if is_admin else "3"):
                print("👋 退出当前用户")
                break

            else:
                print("❌ 无效选择，请重试")


# Dify API地址
BASE_URL = "https://api.dify.ai/v1"
CHAT_ENDPOINT = f"{BASE_URL}/chat-messages"
FILE_UPLOAD_ENDPOINT = f"{BASE_URL}/files/upload"

if __name__ == "__main__":
    main()