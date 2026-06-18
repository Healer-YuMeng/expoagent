<template>
  <div class="teacher-layout">
    <!-- 颜料流动背景 -->
    <PaintBackground />

    <!-- 侧边栏 -->
    <aside class="sidebar glass">
      <!-- Logo区域 -->
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon">🎓</div>
          <div class="logo-text">
            <div class="logo-title">{{ t('teacher.layout.logo') }}</div>
            <div class="logo-subtitle">{{ t('teacher.layout.subtitle') }}</div>
          </div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <nav class="nav-menu">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <div class="nav-icon">{{ item.icon }}</div>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <!-- 用户信息栏 -->
      <div class="sidebar-footer">
        <!-- 语言切换按钮 -->
        <button class="language-btn" @click="toggleLanguage" :title="t('teacher.layout.language')">
          <span class="language-icon">🌐</span>
          <span class="language-text">{{ locale === 'zh-CN' ? 'EN' : '中' }}</span>
        </button>
        
        <div class="user-info">
          <div class="user-avatar">👤</div>
          <div class="user-details">
            <div class="user-name">{{ displayUserName }}</div>
            <div class="user-role">
              {{
                authStore.userRole === 'super_admin'
                  ? t('teacher.layout.userRoleSuper')
                  : authStore.userRole === 'school_admin'
                    ? t('teacher.layout.userRoleAdmin')
                    : t('teacher.layout.userRole')
              }}
            </div>
          </div>
        </div>
        <button class="logout-btn" @click="handleLogout" :title="t('teacher.layout.logout')">
          <span class="logout-icon">🚪</span>
          <span class="logout-text">{{ t('teacher.layout.logout') }}</span>
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-wrapper">
      <!-- 内容区 -->
      <main class="content-area">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useAuthStore } from '@/stores/auth';
import PaintBackground from './PaintBackground.vue';

const route = useRoute();
const authStore = useAuthStore();
const { t, locale } = useI18n();

interface MenuItem {
  path: string;
  labelKey: string;
  icon: string;
  roles?: Array<'teacher' | 'school_admin' | 'super_admin'>;
}

const menuItemsConfig: MenuItem[] = [
  { path: '/teacher/dashboard', labelKey: 'teacher.layout.menu.dashboard', icon: '📊' },
  { path: '/teacher/leads', labelKey: 'teacher.layout.menu.leads', icon: '📋' },
  { path: '/teacher/manual-callbacks', labelKey: 'teacher.layout.menu.manualCallbacks', icon: '⚠️' },
  { path: '/teacher/knowledge-base', labelKey: 'teacher.layout.menu.knowledgeBase', icon: '📚', roles: ['school_admin'] },
  { path: '/teacher/system-prompt', labelKey: 'teacher.layout.menu.systemPrompt', icon: '🧭', roles: ['school_admin', 'super_admin'] },
  { path: '/teacher/users', labelKey: 'teacher.layout.menu.userMgmt', icon: '👥', roles: ['school_admin', 'super_admin'] },
  { path: '/teacher/system-settings', labelKey: 'teacher.layout.menu.systemSettings', icon: '⚙️' },
];

const menuItems = computed(() => 
  menuItemsConfig
    .filter(item => {
      const role = authStore.userRole;
      if (!item.roles) return true;
      return role ? item.roles.includes(role as any) : false;
    })
    .map(item => ({
      ...item,
      label: t(item.labelKey)
    }))
);

const displayUserName = computed(() => {
  const name = authStore.user?.name;
  if (!name) {
    return '13800000002';
  }
  if (name === '默认学校管理员' || name === 'Default School Admin') {
    return t('teacher.layout.defaultSchoolAdmin');
  }
  if (name === '默认超级管理员' || name === 'Default Super Admin') {
    return t('teacher.layout.defaultSuperAdmin');
  }
  return name;
});

const isActive = (path: string) => {
  return route.path === path || route.path.startsWith(path + '/');
};

const handleLogout = () => {
  authStore.logout();
};

const toggleLanguage = () => {
  locale.value = locale.value === 'zh-CN' ? 'en' : 'zh-CN';
  localStorage.setItem('selectedLanguage', locale.value);
};
</script>

<style scoped>
.teacher-layout {
  display: flex;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

/* 毛玻璃效果 */
.glass {
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
}

/* 侧边栏 */
.sidebar {
  width: 260px;
  position: fixed;
  left: 20px;
  top: 20px;
  bottom: 20px;
  border-radius: 25px;
  display: flex;
  flex-direction: column;
  z-index: 100;
  overflow: hidden;
}

/* Logo区域 */
.sidebar-header {
  padding: 30px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.3);
}

.logo {
  display: flex;
  align-items: center;
  gap: 15px;
}

.logo-icon {
  font-size: 42px;
  line-height: 1;
}

.logo-text {
  flex: 1;
}

.logo-title {
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 4px;
}

.logo-subtitle {
  font-size: 12px;
  color: rgba(44, 62, 80, 0.6);
  font-weight: 500;
}

/* 导航菜单 */
.nav-menu {
  flex: 1;
  padding: 20px 15px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  min-height: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 16px 20px;
  border-radius: 15px;
  color: rgba(44, 62, 80, 0.7);
  text-decoration: none;
  transition: all 0.3s ease;
  position: relative;
  font-weight: 500;
  font-size: 15px;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.4);
  color: #2c3e50;
  transform: translateX(5px);
}

.nav-item.active {
  background: rgba(255, 255, 255, 0.6);
  color: #2c3e50;
  font-weight: 600;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 70%;
  background: linear-gradient(to bottom, #3498db, #2980b9);
  border-radius: 0 2px 2px 0;
}

.nav-icon {
  font-size: 24px;
  line-height: 1;
}

.nav-label {
  flex: 1;
}

/* 侧边栏底部 - 用户信息 */
.sidebar-footer {
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.3);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 语言切换按钮 */
.language-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 12px;
  border: none;
  background: rgba(52, 152, 219, 0.15);
  color: #2980b9;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  width: 100%;
}

.language-btn:hover {
  background: rgba(52, 152, 219, 0.25);
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(52, 152, 219, 0.2);
}

.language-icon {
  font-size: 16px;
  line-height: 1;
}

.language-text {
  line-height: 1;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.3);
}

.user-avatar {
  font-size: 32px;
  line-height: 1;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 50%;
}

.user-details {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 15px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 12px;
  color: rgba(44, 62, 80, 0.6);
  font-weight: 500;
}

.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 12px;
  border: none;
  background: rgba(231, 76, 60, 0.15);
  color: #c0392b;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
  width: 100%;
}

.logout-btn:hover {
  background: rgba(231, 76, 60, 0.25);
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(231, 76, 60, 0.2);
}

.logout-icon {
  font-size: 18px;
  line-height: 1;
}

.logout-text {
  line-height: 1;
}

/* 主内容区 */
.main-wrapper {
  flex: 1;
  margin-left: 300px;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* 内容区 */
.content-area {
  flex: 1;
  padding: 20px 20px 20px 0;
  margin-right: 20px;
  margin-top: 20px;
  position: relative;
  z-index: 10;
}

/* 滚动条样式 */
.nav-menu::-webkit-scrollbar {
  width: 6px;
}

.nav-menu::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

.nav-menu::-webkit-scrollbar-thumb {
  background: rgba(44, 62, 80, 0.2);
  border-radius: 3px;
}

.nav-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(44, 62, 80, 0.3);
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .sidebar {
    width: 80px;
    left: 10px;
    top: 10px;
    bottom: 10px;
  }

  .logo-text,
  .nav-label {
    display: none;
  }

  .logo {
    justify-content: center;
  }

  .nav-item {
    justify-content: center;
    padding: 16px;
  }

  .nav-item.active::before {
    width: 3px;
  }

  .main-wrapper {
    margin-left: 110px;
  }

  /* 侧边栏底部响应式 */
  .sidebar-footer {
    padding: 15px 10px;
  }

  .language-btn {
    padding: 8px;
    gap: 0;
  }

  .language-text {
    display: none;
  }

  .language-icon {
    font-size: 18px;
  }

  .user-info {
    flex-direction: column;
    padding: 10px;
    gap: 8px;
  }

  .user-avatar {
    width: 36px;
    height: 36px;
    font-size: 24px;
  }

  .user-details {
    display: none;
  }

  .logout-btn {
    padding: 10px;
    gap: 0;
  }

  .logout-text {
    display: none;
  }

  .logout-icon {
    font-size: 20px;
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 70px;
    border-radius: 15px;
  }

  .sidebar-header {
    padding: 20px 10px;
  }

  .logo-icon {
    font-size: 32px;
  }

  .nav-menu {
    padding: 15px 8px;
  }

  .nav-icon {
    font-size: 20px;
  }

  .main-wrapper {
    margin-left: 90px;
  }

  .content-area {
    padding: 15px 10px 15px 0;
    margin-right: 10px;
    margin-top: 15px;
  }

  /* 侧边栏底部移动端样式 */
  .sidebar-footer {
    padding: 12px 8px;
  }

  .language-btn {
    padding: 8px;
  }

  .language-icon {
    font-size: 16px;
  }

  .user-avatar {
    width: 32px;
    height: 32px;
    font-size: 20px;
  }
}
</style>
