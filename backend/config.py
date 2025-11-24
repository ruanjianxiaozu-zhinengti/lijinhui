from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Dify配置
API_KEY = "app-ThkEAGZSicYWuSGc7ATBEDPw"
API_URL = "https://api.dify.ai/v1/chat-messages"

# 存储用户会话
user_conversations = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'default_user')
        message = data.get('message')

        if not message:
            return jsonify({'success': False, 'error': '消息不能为空'})

        # 初始化用户会话
        if user_id not in user_conversations:
            user_conversations[user_id] = {'conversation_id': None}

        # 调用Dify API
        payload = {
            "inputs": {},
            "query": message,
            "response_mode": "blocking",
            "user": user_id
        }

        # 如果有之前的会话ID，继续对话
        if user_conversations[user_id]['conversation_id']:
            payload["conversation_id"] = user_conversations[user_id]['conversation_id']

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

        # 保存会话ID用于多轮对话
        conversation_id = result.get("conversation_id")
        if conversation_id:
            user_conversations[user_id]['conversation_id'] = conversation_id

        # 获取回答
        answer = result.get("answer", "抱歉，我没有理解您的问题。")

        return jsonify({
            'success': True,
            'answer': answer,
            'conversation_id': conversation_id
        })

    except Exception as e:
        print(f"API调用错误: {e}")
        return jsonify({
            'success': False,
            'error': f'请求失败: {str(e)}'
        })


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': '服务正常'})


if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')