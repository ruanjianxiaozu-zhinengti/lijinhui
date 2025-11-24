// API基础配置
const API_BASE_URL = 'http://localhost:5000/api';

// 通用请求函数
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }

  try {
    const response = await fetch(url, config);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('API请求错误:', error);
    return { success: false, message: '网络请求失败' };
  }
}

// 用户认证API
const authAPI = {
  async login(account, password) {
    return await apiRequest('/login', {
      method: 'POST',
      body: { account, password }
    });
  },

  async register(account, password) {
    return await apiRequest('/register', {
      method: 'POST',
      body: { account, password }
    });
  }
};

// 聊天API
const chatAPI = {
  async sendMessage(userId, message, conversationId = null) {
    return await apiRequest('/chat', {
      method: 'POST',
      body: { user_id: userId, message, conversation_id: conversationId }
    });
  },

  async uploadFile(userId, file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);

    try {
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
      return await response.json();
    } catch (error) {
      console.error('文件上传错误:', error);
      return { success: false, message: '文件上传失败' };
    }
  },

  async getHistory(userId) {
    return await apiRequest(`/history/${userId}`);
  }
};

// 管理API
const adminAPI = {
  async getUsers() {
    return await apiRequest('/users');
  },

  async getStats() {
    return await apiRequest('/stats');
  },

  async deleteUser(userId) {
    return await apiRequest(`/delete_user/${userId}`, {
      method: 'DELETE'
    });
  },

  async deleteUserChat(userId) {
    return await apiRequest(`/delete_chat/${userId}`, {
      method: 'DELETE'
    });
  }
};

// 对话管理API
const conversationAPI = {
  async getConversations(userId) {
    return await apiRequest(`/conversations/${userId}`);
  },

  async getConversation(userId, date) {
    return await apiRequest(`/conversation/${userId}/${date}`);
  },

  async exportConversation(userId, date) {
    return await apiRequest(`/conversation/export/${userId}/${date}`);
  },

  async deleteConversation(userId, date) {
    return await apiRequest(`/conversation/delete/${userId}/${date}`, {
      method: 'DELETE'
    });
  }
};