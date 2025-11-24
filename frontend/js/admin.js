// 直接从全局作用域获取API
const { adminAPI } = window;

const { createApp } = Vue;

createApp({
  data() {
    return {
      currentUser: {
        id: null,
        account: '',
        is_admin: false
      },
      users: [],
      stats: {},
      userStats: [],
      loading: false
    };
  },
  methods: {
    async checkAdmin() {
      // 从sessionStorage获取用户信息
      const userStr = sessionStorage.getItem('currentUser');
      if (!userStr) {
        alert('请先登录');
        window.location.href = 'index.html';
        return;
      }

      const user = JSON.parse(userStr);
      if (!user.is_admin) {
        alert('无权限访问管理后台');
        window.location.href = 'index.html';
        return;
      }

      this.currentUser = user;
      await this.loadData();
    },

    async loadData() {
      this.loading = true;
      
      // 加载用户列表
      const usersResult = await adminAPI.getUsers();
      if (usersResult.success) {
        this.users = usersResult.users;
      }

      // 加载统计信息
      const statsResult = await adminAPI.getStats();
      if (statsResult.success) {
        this.stats = statsResult.stats;
        this.userStats = statsResult.stats.user_stats || [];
      }

      this.loading = false;
    },

    async refreshData() {
      await this.loadData();
    },

    async deleteUser(userId) {
      if (!confirm('确定要删除这个用户吗？此操作不可恢复！')) {
        return;
      }

      if (userId === this.currentUser.id) {
        alert('不能删除当前登录的用户');
        return;
      }

      const result = await adminAPI.deleteUser(userId);
      if (result.success) {
        alert('用户删除成功');
        await this.loadData();
      } else {
        alert('用户删除失败');
      }
    },

    async clearUserChat(userId) {
      if (!confirm('确定要清空这个用户的所有对话记录吗？')) {
        return;
      }

      const result = await adminAPI.deleteUserChat(userId);
      if (result.success) {
        alert('对话记录清空成功');
        await this.loadData();
      } else {
        alert('对话记录清空失败');
      }
    },

    getUserChatCount(userId) {
      const stat = this.userStats.find(s => {
        // 找到对应用户的统计信息
        const user = this.users.find(u => u.id === userId);
        return user && s.account === user.account;
      });
      return stat ? stat.chat_count : 0;
    },

    getProgressWidth(chatCount) {
      const maxChats = Math.max(...this.userStats.map(s => s.chat_count), 1);
      return `${(chatCount / maxChats) * 100}%`;
    },

    formatDate(dateStr) {
      if (!dateStr) return '';
      return new Date(dateStr).toLocaleDateString('zh-CN');
    },

    goBack() {
      window.location.href = 'index.html';
    },

    logout() {
      sessionStorage.removeItem('currentUser');
      window.location.href = 'index.html';
    }
  },

  mounted() {
    this.checkAdmin();
  }
}).mount("#admin-app");