// 聊天应用主逻辑
const { createApp } = Vue;

createApp({
  data() {
    return {
      // 用户相关
      currentUser: {
        id: null,
        account: '',
        is_admin: false
      },
      showLoginModal: true,
      loginTab: 'login',
      loginForm: {
        account: '',
        password: ''
      },
      registerForm: {
        account: '',
        password: '',
        confirmPassword: ''
      },
      loading: false,

      // 聊天相关
      messages: [
        {
          role: 'system',
          text: '欢迎使用多轮问答系统！请输入您的问题或上传文件进行分析。',
          timestamp: new Date()
        }
      ],
      input: '',
      conversationId: null,
      showHistory: false,
      history: [],
      sidebarOpen: false,

      // 新增对话相关数据
      conversations: [],
      currentConversationId: null,
      currentConversationDate: null
    };
  },
  computed: {
    userInitials() {
      if (!this.currentUser.account) return '?';
      return this.currentUser.account.charAt(0).toUpperCase();
    },

    // 计算显示的会话列表，用于生成会话编号
    displayConversations() {
      return this.conversations.map((conversation, index) => {
        return {
          ...conversation,
          displayIndex: this.conversations.length - index // 倒序编号，最新的会话编号最大
        };
      });
    }
  },
  methods: {
    // 用户认证
    async login() {
      if (!this.loginForm.account || !this.loginForm.password) {
        alert('请输入账号和密码');
        return;
      }

      this.loading = true;
      const result = await authAPI.login(this.loginForm.account, this.loginForm.password);
      this.loading = false;

      if (result.success) {
        this.currentUser = result.user;
        this.showLoginModal = false;
        sessionStorage.setItem('currentUser', JSON.stringify(result.user));
        this.loadConversations(); // 加载对话列表
        this.loadHistory();
      } else {
        alert(result.message);
      }
    },

    async register() {
      if (!this.registerForm.account || !this.registerForm.password) {
        alert('请输入账号和密码');
        return;
      }

      if (this.registerForm.password !== this.registerForm.confirmPassword) {
        alert('两次输入的密码不一致');
        return;
      }

      this.loading = true;
      const result = await authAPI.register(this.registerForm.account, this.registerForm.password);
      this.loading = false;

      if (result.success) {
        alert('注册成功，请登录');
        this.loginTab = 'login';
        this.loginForm.account = this.registerForm.account;
        this.registerForm = { account: '', password: '', confirmPassword: '' };
      } else {
        alert(result.message);
      }
    },

    logout() {
      this.currentUser = { id: null, account: '', is_admin: false };
      this.messages = [{
        role: 'system',
        text: '欢迎使用多轮问答系统！请输入您的问题或上传文件进行分析。',
        timestamp: new Date()
      }];
      this.history = [];
      this.conversations = [];
      this.showLoginModal = true;
      this.conversationId = null;
      this.currentConversationId = null;
      this.currentConversationDate = null;
      sessionStorage.removeItem('currentUser');
    },

    // 聊天功能
    async sendMessage() {
      if (!this.input.trim() || this.loading) return;

      const userMessage = this.input.trim();
      this.input = '';

      this.messages.push({
        role: 'user',
        text: userMessage,
        timestamp: new Date()
      });

      this.loading = true;
      this.scrollToBottom();

      const result = await chatAPI.sendMessage(this.currentUser.id, userMessage, this.conversationId);
      this.loading = false;

      if (result.success) {
        this.messages.push({
          role: 'system',
          text: result.response,
          timestamp: new Date()
        });
        this.conversationId = result.conversation_id;
        this.loadHistory();
        // 发送消息后重新加载对话列表
        await this.loadConversations();
      } else {
        this.messages.push({
          role: 'system',
          text: `错误: ${result.message}`,
          timestamp: new Date()
        });
      }

      this.scrollToBottom();
    },

    async handleFileUpload(event) {
      const file = event.target.files[0];
      if (!file) return;

      const allowedTypes = ['.txt', '.pdf', '.png', '.jpg', '.jpeg'];
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      if (!allowedTypes.includes(fileExtension)) {
        alert('不支持的文件格式，请上传 TXT、PDF、PNG 或 JPG 文件');
        return;
      }

      this.loading = true;

      this.messages.push({
        role: 'user',
        text: `上传文件: ${file.name}`,
        timestamp: new Date()
      });

      this.messages.push({
        role: 'system',
        text: '正在分析文件内容...',
        timestamp: new Date()
      });

      this.scrollToBottom();

      const result = await chatAPI.uploadFile(this.currentUser.id, file);
      this.loading = false;

      if (result.success) {
        this.messages.pop();
        this.messages.push({
          role: 'system',
          text: result.response,
          timestamp: new Date()
        });
        this.conversationId = result.conversation_id;
        this.loadHistory();
        // 文件上传后重新加载对话列表
        await this.loadConversations();
      } else {
        this.messages.pop();
        this.messages.push({
          role: 'system',
          text: `文件分析失败: ${result.message}`,
          timestamp: new Date()
        });
      }

      event.target.value = '';
      this.scrollToBottom();
    },

    async loadHistory() {
      if (!this.currentUser.id) return;

      const result = await chatAPI.getHistory(this.currentUser.id);
      if (result.success) {
        this.history = result.history;
      }
    },

    clearChat() {
      if (confirm('确定要清空当前对话吗？')) {
        this.messages = [{
          role: 'system',
          text: '对话已清空，请输入您的问题。',
          timestamp: new Date()
        }];
        this.conversationId = null;
        this.currentConversationId = null;
        this.currentConversationDate = null;
      }
    },

    // 对话管理功能
    async loadConversations() {
      if (!this.currentUser.id) return;

      try {
        const result = await conversationAPI.getConversations(this.currentUser.id);
        if (result.success) {
          this.conversations = result.conversations;
        } else {
          console.error('加载对话列表失败:', result.message);
        }
      } catch (error) {
        console.error('加载对话列表错误:', error);
      }
    },

    async selectConversation(conversation) {
      this.currentConversationId = conversation.id;
      this.currentConversationDate = conversation.date;

      // 加载该对话的详细记录
      const result = await conversationAPI.getConversation(this.currentUser.id, conversation.date);
      if (result.success) {
        this.messages = result.messages;
        this.showHistory = false;
        this.scrollToBottom();
      } else {
        alert('加载对话失败: ' + result.message);
      }
    },

    newSession() {
      this.currentConversationId = null;
      this.currentConversationDate = null;
      this.messages = [{
        role: 'system',
        text: '新对话已开始，请输入您的问题或上传文件进行分析。',
        timestamp: new Date()
      }];
      this.conversationId = null;
      this.showHistory = false;

      // 确保左侧只显示"当前会话"为激活状态
      this.$nextTick(() => {
        this.scrollToBottom();
      });
    },

    // 格式化会话索引显示
    formatSessionIndex(index) {
      return index;
    },

    // 格式化预览文本
    formatPreview(conversation) {
      // 如果有预览文本则使用，否则使用默认文本
      return conversation.preview || '信息安全咨询';
    },

    async exportConversation(conversation) {
      try {
        const result = await conversationAPI.exportConversation(this.currentUser.id, conversation.date);
        if (result.success) {
          // 创建下载链接
          const blob = new Blob([result.content], { type: 'text/plain;charset=utf-8' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = result.filename || `conversation_${conversation.date}.txt`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        } else {
          alert('导出失败: ' + result.message);
        }
      } catch (error) {
        console.error('导出对话错误:', error);
        alert('导出对话时发生错误');
      }
    },

    async deleteConversation(conversation) {
      if (!confirm(`确定要删除会话 ${this.formatSessionIndex(conversation.displayIndex)} 的所有对话记录吗？此操作不可恢复！`)) {
        return;
      }

      try {
        const result = await conversationAPI.deleteConversation(this.currentUser.id, conversation.date);
        if (result.success) {
          alert('对话记录删除成功');
          // 重新加载对话列表
          await this.loadConversations();
          // 如果删除的是当前查看的对话，切换到新对话
          if (this.currentConversationDate === conversation.date) {
            this.newSession();
          }
        } else {
          alert('删除失败: ' + result.message);
        }
      } catch (error) {
        console.error('删除对话错误:', error);
        alert('删除对话时发生错误');
      }
    },

    formatRelativeTime(dateStr) {
      if (!dateStr) return '';

      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return '刚刚';
      if (diffMins < 60) return `${diffMins}分钟前`;
      if (diffHours < 24) return `${diffHours}小时前`;
      if (diffDays < 7) return `${diffDays}天前`;

      return date.toLocaleDateString('zh-CN');
    },

    // 辅助功能
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.chatContainer;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },

    formatTime(date) {
      if (!date) return '';
      if (typeof date === 'string') {
        date = new Date(date);
      }
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      });
    },

    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen;
    },

    goToAdmin() {
      window.location.href = 'admin.html';
    }
  },

  mounted() {
    const savedUser = sessionStorage.getItem('currentUser');
    if (savedUser) {
      this.currentUser = JSON.parse(savedUser);
      this.showLoginModal = false;
      this.loadConversations(); // 加载对话列表
      this.loadHistory();
    }

    this.scrollToBottom();
  }
}).mount("#app");