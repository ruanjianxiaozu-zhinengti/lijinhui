from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
import requests
import uuid
from database.dify_chat_system import Database

app = Flask(__name__)
CORS(app)

# 配置
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Dify配置 - 请确保使用有效的API密钥
API_KEY = "app-zAqLCfALuFUIvGThnFi0xZJm"
BASE_URL = "https://api.dify.ai/v1"
CHAT_ENDPOINT = f"{BASE_URL}/chat-messages"
FILE_UPLOAD_ENDPOINT = f"{BASE_URL}/files/upload"

# 网络配置
TIMEOUT = 60
RETRY_COUNT = 3
RETRY_DELAY = 3
VERIFY_SSL = False

class DifyClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def upload_file(self, file_path):
        if not os.path.exists(file_path):
            return None, None, "文件不存在"

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
                    time.sleep(RETRY_DELAY)
                else:
                    return None, None, f"上传失败 [{response.status_code}]"
            except Exception as e:
                if retry < RETRY_COUNT:
                    time.sleep(RETRY_DELAY)
                else:
                    return None, None, f"上传错误: {str(e)}"
        return None, None, "达到最大重试次数"

    def chat(self, message, file_id=None, file_type=None, conversation_id=None):
        payload = {
            "query": message,
            "inputs": {},
            "response_mode": "blocking",
            "user": "user1",
            "conversation_id": conversation_id
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
                    return result.get('answer', '无回复'), result.get('conversation_id')
                elif retry < RETRY_COUNT:
                    time.sleep(RETRY_DELAY)
                else:
                    return f"对话失败 [{response.status_code}]: {response.text[:200]}", None
            except Exception as e:
                if retry < RETRY_COUNT:
                    time.sleep(RETRY_DELAY)
                else:
                    return f"对话错误: {str(e)}", None
        return "达到最大重试次数", None

# 初始化数据库和Dify客户端
try:
    db = Database()
    dify = DifyClient(API_KEY)
    print("✅ 系统初始化成功")
except Exception as e:
    print(f"❌ 系统初始化失败: {e}")
    db = None
    dify = None

# API路由
@app.route('/')
def index():
    return jsonify({"message": "Dify Chat System API", "status": "running"})

@app.route('/api/register', methods=['POST'])
def register():
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    data = request.json
    account = data.get('account', '').strip()
    password = data.get('password', '').strip()

    success, message = db.register_user(account, password)
    return jsonify({'success': success, 'message': message})

@app.route('/api/login', methods=['POST'])
def login():
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    data = request.json
    account = data.get('account', '').strip()
    password = data.get('password', '').strip()

    user = db.login_user(account, password)
    if user:
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'account': user['account'],
                'is_admin': user['is_admin']
            }
        })
    else:
        return jsonify({'success': False, 'message': '账号或密码错误'})

@app.route('/api/chat', methods=['POST'])
def chat():
    if not db or not dify:
        return jsonify({'success': False, 'message': '系统未就绪'})

    data = request.json
    user_id = data.get('user_id')
    message = data.get('message')
    conversation_id = data.get('conversation_id')

    if not user_id or not message:
        return jsonify({'success': False, 'message': '参数错误'})

    # 调用Dify API
    response, new_conversation_id = dify.chat(message, conversation_id=conversation_id)

    # 确保响应中有适当的换行（可选，根据实际需要）
    if response and isinstance(response, str):
        # 在标点符号后添加换行，使内容更易读
        response = response.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n')
        # 清理多余的换行
        response = response.replace('\n\n', '\n').replace('\n\n', '\n')

    # 保存对话记录
    db.save_chat(user_id, message, response)

    return jsonify({
        'success': True,
        'response': response,
        'conversation_id': new_conversation_id
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if not db or not dify:
        return jsonify({'success': False, 'message': '系统未就绪'})

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有文件'})

    file = request.files['file']
    user_id = request.form.get('user_id')

    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})

    # 保存文件
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # 上传到Dify
    file_id, file_type, error = dify.upload_file(file_path)
    if error:
        os.remove(file_path)
        return jsonify({'success': False, 'message': error})

    # 调用Dify分析文件
    response, conversation_id = dify.chat("请分析这个文件的内容", file_id, file_type)

    # 保存对话记录
    db.save_chat(user_id, None, response, filename)

    # 删除本地临时文件
    os.remove(file_path)

    return jsonify({
        'success': True,
        'response': response,
        'conversation_id': conversation_id
    })

@app.route('/api/history/<int:user_id>')
def get_history(user_id):
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    history = db.get_chat_history(user_id)
    return jsonify({'success': True, 'history': history})

@app.route('/api/users')
def get_users():
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    users = db.get_all_users()
    return jsonify({'success': True, 'users': users})

@app.route('/api/stats')
def get_stats():
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    stats = db.get_user_stats()
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    success = db.delete_user(user_id)
    return jsonify({'success': success})

@app.route('/api/delete_chat/<int:user_id>', methods=['DELETE'])
def delete_chat(user_id):
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    success = db.delete_user_chat(user_id)
    return jsonify({'success': success})

# 修复后的对话管理API
@app.route('/api/conversations/<int:user_id>')
def get_conversations(user_id):
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    try:
        # 获取用户的所有对话（按时间分组）
        db.cursor.execute('''
        SELECT 
            DATE(create_time) as date,
            COUNT(*) as count,
            MAX(create_time) as last_time
        FROM chat_records 
        WHERE user_id = %s 
        GROUP BY DATE(create_time)
        ORDER BY last_time DESC
        LIMIT 50
        ''', (user_id,))

        date_groups = db.cursor.fetchall()

        conversations = []
        for group in date_groups:
            # 获取该日期下的第一条记录作为预览
            db.cursor.execute('''
            SELECT id, query, response, create_time
            FROM chat_records 
            WHERE user_id = %s AND DATE(create_time) = %s
            ORDER BY create_time DESC
            LIMIT 1
            ''', (user_id, group['date']))

            latest_record = db.cursor.fetchone()
            if latest_record:
                preview = latest_record['query'] or '文件对话'
                if len(preview) > 30:
                    preview = preview[:30] + '...'

                conversations.append({
                    'id': f"date_{group['date']}",
                    'title': f"对话 - {group['date']}",
                    'preview': preview,
                    'count': group['count'],
                    'last_time': group['last_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'date': group['date'].strftime('%Y-%m-%d')  # 使用标准日期格式
                })

        return jsonify({'success': True, 'conversations': conversations})
    except Exception as e:
        print(f"获取对话列表失败: {e}")
        return jsonify({'success': False, 'message': '获取对话列表失败'})

@app.route('/api/conversation/<int:user_id>/<string:date>')  # 改为string类型
def get_conversation_by_date(user_id, date):
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    try:
        # 验证日期格式
        from datetime import datetime
        try:
            conversation_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': '日期格式错误'})

        db.cursor.execute('''
        SELECT id, query, response, file_path, create_time
        FROM chat_records 
        WHERE user_id = %s AND DATE(create_time) = %s
        ORDER BY create_time ASC
        ''', (user_id, conversation_date))

        records = db.cursor.fetchall()

        # 格式化消息
        messages = []
        for record in records:
            if record['query']:
                messages.append({
                    'role': 'user',
                    'text': record['query'],
                    'timestamp': record['create_time'].strftime('%Y-%m-%d %H:%M:%S')
                })

            messages.append({
                'role': 'system',
                'text': record['response'],
                'timestamp': record['create_time'].strftime('%Y-%m-%d %H:%M:%S')
            })

        return jsonify({'success': True, 'messages': messages, 'date': date})
    except Exception as e:
        print(f"获取对话详情失败: {e}")
        return jsonify({'success': False, 'message': '获取对话详情失败'})

@app.route('/api/conversation/export/<int:user_id>/<string:date>')
def export_conversation_api(user_id, date):  # 重命名函数
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    try:
        # 验证日期格式
        from datetime import datetime
        try:
            conversation_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': '日期格式错误'})

        db.cursor.execute('''
        SELECT query, response, file_path, create_time
        FROM chat_records 
        WHERE user_id = %s AND DATE(create_time) = %s
        ORDER BY create_time ASC
        ''', (user_id, conversation_date))

        records = db.cursor.fetchall()

        # 生成TXT内容
        content = f"对话记录 - {date}\n"
        content += "=" * 50 + "\n\n"

        for i, record in enumerate(records, 1):
            content += f"[记录 {i}] {record['create_time']}\n"
            if record['query']:
                content += f"用户: {record['query']}\n"
            if record['file_path']:
                content += f"文件: {record['file_path']}\n"
            content += f"AI: {record['response']}\n"
            content += "-" * 30 + "\n\n"

        return jsonify({'success': True, 'content': content, 'filename': f"对话记录_{date}.txt"})
    except Exception as e:
        print(f"导出对话失败: {e}")
        return jsonify({'success': False, 'message': '导出对话失败'})

@app.route('/api/conversation/delete/<int:user_id>/<string:date>', methods=['DELETE'])
def delete_conversation_api(user_id, date):  # 重命名函数
    if not db:
        return jsonify({'success': False, 'message': '数据库未连接'})

    try:
        # 验证日期格式
        from datetime import datetime
        try:
            conversation_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': '日期格式错误'})

        db.cursor.execute('''
        DELETE FROM chat_records 
        WHERE user_id = %s AND DATE(create_time) = %s
        ''', (user_id, conversation_date))

        db.conn.commit()

        return jsonify({'success': True, 'message': '对话记录删除成功'})
    except Exception as e:
        print(f"删除对话失败: {e}")
        return jsonify({'success': False, 'message': '删除对话失败'})

if __name__ == '__main__':
    if db and dify:
        print("🚀 启动Dify聊天系统API服务器...")
        print("📝 默认管理员账号: 666 / admin")
        print("🌐 API地址: http://localhost:5000")
        app.run(debug=True, port=5000)
    else:
        print("❌ 系统初始化失败，无法启动服务器")