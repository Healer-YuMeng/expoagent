<template>
  <div class="teacher-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="brand-mark" aria-hidden="true">
          <img class="brand-logo" :src="expoHallLogo" alt="" />
        </div>
        <div class="brand-copy">
          <div class="logo-title">{{ t('teacher.layout.logo') }}</div>
          <div class="logo-subtitle">{{ t('teacher.layout.subtitle') }}</div>
        </div>
      </div>

      <nav class="nav-menu">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <span class="nav-active-bar" aria-hidden="true"></span>
          <el-icon class="nav-icon">
            <component :is="item.icon" />
          </el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <button class="language-btn" @click="toggleLanguage" :title="t('teacher.layout.language')">
          <el-icon class="language-icon"><Promotion /></el-icon>
          <span class="language-text">{{ locale === 'zh-CN' ? 'EN' : '中' }}</span>
        </button>

        <div class="user-info">
          <div class="user-avatar" aria-hidden="true">
            <el-icon><UserFilled /></el-icon>
          </div>
          <div class="user-details">
            <div class="user-name">{{ displayUserName }}</div>
            <div class="user-role">
              {{
                authStore.userRole === 'super_admin'
                  ? t('teacher.layout.userRoleSuper')
                  : authStore.userRole === 'admin'
                    ? t('teacher.layout.userRoleAdmin')
                    : t('teacher.layout.userRole')
              }}
            </div>
          </div>
        </div>

        <button class="logout-btn" @click="handleLogout" :title="t('teacher.layout.logout')">
          <el-icon class="logout-icon"><SwitchButton /></el-icon>
          <span class="logout-text">{{ t('teacher.layout.logout') }}</span>
        </button>
      </div>
    </aside>

    <div class="main-wrapper">
      <main class="content-area" :class="{ 'content-area--locked': isFeatureLocked }">
        <div class="content-shell" :class="{ 'content-shell--locked': isFeatureLocked }">
          <router-view />
          <div
            v-if="isFeatureLocked"
            class="feature-lock-overlay"
            @wheel.prevent
            @touchmove.prevent
          >
            <div class="feature-lock-card">
              <div class="feature-lock-title">{{ t('teacher.layout.featureLockedTitle') }}</div>
              <div class="feature-lock-desc">{{ t('teacher.layout.featureLockedDesc') }}</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { Component } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import {
  Collection,
  DataAnalysis,
  Document,
  MessageBox,
  Promotion,
  Setting,
  SwitchButton,
  User,
  UserFilled,
  Warning,
} from '@element-plus/icons-vue';
import { useAuthStore } from '@/stores/auth';
import {
  getPortalPath,
  isPortalMenuPathActive,
  isSchoolAdminFeatureLocked,
} from '@/router/portalRoutes';
import expoHallLogo from '@/assets/expo-hall-logo.png';

const route = useRoute();
const authStore = useAuthStore();
const { t, locale } = useI18n();

interface MenuItem {
  path: string;
  labelKey: string;
  icon: Component;
  roles?: Array<'sales' | 'admin' | 'super_admin'>;
}

const menuItemsConfig: Array<Omit<MenuItem, 'path'> & { target: 'dashboard' | 'leads' | 'manualCallbacks' | 'knowledgeBase' | 'systemPrompt' | 'userManagement' | 'systemSettings' }> = [
  { target: 'dashboard', labelKey: 'teacher.layout.menu.dashboard', icon: DataAnalysis },
  { target: 'leads', labelKey: 'teacher.layout.menu.leads', icon: Document },
  { target: 'manualCallbacks', labelKey: 'teacher.layout.menu.manualCallbacks', icon: Warning },
  { target: 'knowledgeBase', labelKey: 'teacher.layout.menu.knowledgeBase', icon: Collection, roles: ['sales', 'admin'] },
  { target: 'systemPrompt', labelKey: 'teacher.layout.menu.systemPrompt', icon: MessageBox, roles: ['admin', 'super_admin'] },
  { target: 'userManagement', labelKey: 'teacher.layout.menu.userMgmt', icon: User, roles: ['admin', 'super_admin'] },
  { target: 'systemSettings', labelKey: 'teacher.layout.menu.systemSettings', icon: Setting },
];

const menuItems = computed(() =>
  menuItemsConfig
    .filter((item) => {
      const role = authStore.userRole;
      if (!item.roles) return true;
      return role ? item.roles.includes(role as any) : false;
    })
    .map((item) => ({
      ...item,
      path: getPortalPath(authStore.userRole, item.target),
      label: t(item.labelKey),
    }))
);

const displayUserName = computed(() => {
  const name = authStore.user?.name;
  if (!name) {
    return '13800000002';
  }
  if (name === '默认学校管理员' || name === '默认普通管理员' || name === 'Default School Admin' || name === 'Default Admin') {
    return t('teacher.layout.defaultSchoolAdmin');
  }
  if (name === '默认超级管理员' || name === 'Default Super Admin') {
    return t('teacher.layout.defaultSuperAdmin');
  }
  return name;
});

const isActive = (path: string) => isPortalMenuPathActive(route.path, path);
const isFeatureLocked = computed(() => isSchoolAdminFeatureLocked(authStore.userRole, route.path));

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
  position: relative;
  display: flex;
  min-height: 100vh;
  overflow: hidden;
  background: #f6f7f9;
}

.sidebar {
  position: fixed;
  top: 18px;
  left: 18px;
  bottom: 18px;
  z-index: 100;
  display: flex;
  width: 292px;
  flex-direction: column;
  border: 1px solid #e6eaf0;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 26px 24px 22px;
}

.brand-mark {
  display: grid;
  width: 60px;
  height: 60px;
  place-items: center;
  flex-shrink: 0;
}

.brand-logo {
  display: block;
  width: 60px;
  height: 60px;
  object-fit: contain;
}

.brand-copy {
  min-width: 0;
}

.logo-title {
  color: #273142;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
}

.logo-subtitle {
  margin-top: 4px;
  color: #7a8595;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
}

.nav-menu {
  flex: 1;
  padding: 8px 14px 18px;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 60px;
  margin-bottom: 8px;
  padding: 0 20px;
  border-radius: 18px;
  color: #6c7c92;
  text-decoration: none;
  transition:
    background-color 0.22s ease,
    color 0.22s ease,
    transform 0.22s ease,
    box-shadow 0.22s ease;
}

.nav-item:hover {
  background: #f6f7f9;
  color: #2d3646;
  transform: translateX(2px);
}

.nav-item.active {
  background: #f1f3f6;
  color: #243041;
  box-shadow: inset 0 0 0 1px #e5e9ef;
}

.nav-active-bar {
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 5px;
  border-radius: 0 999px 999px 0;
  background: #1f2c3d;
  opacity: 0;
  transition: opacity 0.22s ease;
}

.nav-item.active .nav-active-bar {
  opacity: 1;
}

.nav-icon {
  flex-shrink: 0;
  color: currentColor;
  font-size: 24px;
}

.nav-label {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 18px 20px;
  border-top: 1px solid #edf0f4;
}

.language-btn,
.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 52px;
  border: 1px solid #e2e7ee;
  border-radius: 16px;
  background: #ffffff;
  color: #314156;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.22s ease,
    box-shadow 0.22s ease,
    transform 0.22s ease,
    color 0.22s ease;
}

.language-btn:hover,
.logout-btn:hover {
  border-color: #d5dce5;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
  transform: translateY(-1px);
}

.language-icon,
.logout-icon {
  font-size: 18px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1px solid #e2e7ee;
  border-radius: 18px;
  background: #fbfcfd;
}

.user-avatar {
  display: grid;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  place-items: center;
  border-radius: 50%;
  background: #f0f2f5;
  color: #506177;
  font-size: 24px;
}

.user-details {
  min-width: 0;
  flex: 1;
}

.user-name {
  color: #283141;
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  margin-top: 4px;
  color: #8691a0;
  font-size: 13px;
  font-weight: 600;
}

.main-wrapper {
  flex: 1;
  min-height: 100vh;
  margin-left: 328px;
  border-left: 1px solid #e9edf2;
}

.content-area {
  position: relative;
  z-index: 10;
  min-height: 100vh;
  padding: 18px;
}

.content-area--locked {
  height: 100vh;
  overflow: hidden;
}

.content-shell {
  position: relative;
  min-height: calc(100vh - 36px);
}

.content-shell--locked {
  overflow: hidden;
}

.feature-lock-overlay {
  position: absolute;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  border-radius: 28px;
  background: rgba(246, 248, 251, 0.7);
  backdrop-filter: blur(6px);
  pointer-events: all;
}

.feature-lock-card {
  max-width: 420px;
  padding: 28px 32px;
  border: 1px solid rgba(207, 216, 228, 0.95);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 22px 48px rgba(31, 44, 61, 0.12);
  text-align: center;
}

.feature-lock-title {
  color: #233145;
  font-size: 24px;
  font-weight: 800;
  line-height: 1.35;
}

.feature-lock-desc {
  margin-top: 10px;
  color: #728095;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.7;
}

.nav-menu::-webkit-scrollbar {
  width: 6px;
}

.nav-menu::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(185, 195, 208, 0.95);
}

.nav-menu::-webkit-scrollbar-track {
  background: transparent;
}

@media (max-width: 1280px) {
  .sidebar {
    width: 248px;
  }

  .main-wrapper {
    margin-left: 284px;
  }
}

@media (max-width: 1024px) {
  .sidebar {
    width: 94px;
    padding-top: 8px;
  }

  .sidebar-header {
    justify-content: center;
    padding: 20px 12px 18px;
  }

  .brand-copy,
  .nav-label,
  .language-text,
  .user-details,
  .logout-text {
    display: none;
  }

  .nav-menu {
    padding: 8px 10px 16px;
  }

  .nav-item {
    justify-content: center;
    padding: 0;
  }

  .sidebar-footer {
    padding: 16px 12px 18px;
  }

  .user-info {
    justify-content: center;
    padding: 12px 10px;
  }

  .main-wrapper {
    margin-left: 120px;
  }
}

@media (max-width: 768px) {
  .sidebar {
    left: 10px;
    top: 10px;
    bottom: 10px;
    width: 78px;
    border-radius: 22px;
  }

  .brand-mark {
    width: 46px;
    height: 46px;
    border-radius: 14px;
  }

  .nav-item {
    min-height: 54px;
  }

  .nav-icon {
    font-size: 21px;
  }

  .language-btn,
  .logout-btn {
    min-height: 46px;
  }

  .user-avatar {
    width: 42px;
    height: 42px;
    font-size: 20px;
  }

  .main-wrapper {
    margin-left: 96px;
  }

  .content-area {
    padding: 10px;
  }

  .content-shell {
    min-height: calc(100vh - 20px);
  }

  .feature-lock-card {
    max-width: 100%;
    padding: 24px 20px;
    border-radius: 20px;
  }

  .feature-lock-title {
    font-size: 20px;
  }
}
</style>
