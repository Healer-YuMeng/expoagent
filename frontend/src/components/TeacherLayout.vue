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
      <div class="sidebar-divider" aria-hidden="true"></div>

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
        <div class="user-info">
          <div class="user-avatar" aria-hidden="true">
            <el-icon><UserFilled /></el-icon>
          </div>
          <div class="user-details">
            <div class="user-name-row">
              <div class="user-name">{{ displayUserName }}</div>
              <div class="user-role">{{ currentUserRoleLabel }}</div>
              <el-dropdown trigger="click" placement="top-end" @command="handleAccountMenuCommand">
                <button class="account-more-btn" type="button" :title="t('teacher.layout.accountMenu')">
                  <el-icon><MoreFilled /></el-icon>
                </button>
                <template #dropdown>
                  <el-dropdown-menu class="account-dropdown-menu">
                    <el-dropdown-item command="profile">
                      <el-icon><User /></el-icon>
                      <span>{{ t('teacher.layout.accountManagement') }}</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
        <div class="footer-action-row">
          <button class="language-btn" @click="toggleLanguage" :title="t('teacher.layout.language')">
            <el-icon class="language-icon"><Promotion /></el-icon>
            <span class="language-text">{{ locale === 'zh-CN' ? 'EN' : '中' }}</span>
          </button>

          <button class="logout-btn" @click="handleLogout" :title="t('teacher.layout.logout')">
            <el-icon class="logout-icon"><SwitchButton /></el-icon>
            <span class="logout-text">{{ t('teacher.layout.logout') }}</span>
          </button>
        </div>
      </div>
    </aside>

    <el-dialog
      v-model="profileDialogVisible"
      class="profile-dialog"
      :title="t('teacher.layout.profileTitle')"
      width="708px"
      modal-class="profile-dialog-mask"
    >
      <div class="profile-dialog-body">
        <aside class="profile-side-nav">
          <button class="profile-side-item profile-side-item--active" type="button">
            <el-icon><User /></el-icon>
            <span>{{ t('teacher.layout.profileEntry') }}</span>
          </button>
        </aside>

        <section class="profile-content">
          <div class="profile-info-table">
            <div class="profile-info-row">
              <div class="profile-info-label">{{ t('teacher.layout.profileAccount') }}</div>
              <div class="profile-info-value">{{ currentAccountValue }}</div>
            </div>
            <div class="profile-info-row">
              <div class="profile-info-label">{{ t('teacher.layout.profileName') }}</div>
              <div class="profile-info-value">{{ displayUserName }}</div>
            </div>
            <div class="profile-info-row">
              <div class="profile-info-label">{{ t('teacher.layout.profileRole') }}</div>
              <div class="profile-info-value">{{ currentUserRoleLabel }}</div>
            </div>
          </div>
        </section>
      </div>
    </el-dialog>

    <div class="main-wrapper">
      <main class="content-area" :class="{ 'content-area--locked': isFeatureLocked }">
        <div v-if="showFeatureGateControl" class="feature-gate-control">
          <div class="feature-gate-copy">
            <div class="feature-gate-title">{{ t('teacher.layout.featureGateTitle') }}</div>
            <div class="feature-gate-desc">
              {{ t('teacher.layout.featureGateDesc', { module: currentFeatureGateLabel }) }}
            </div>
          </div>
          <label
            class="feature-gate-switch"
            :class="{ 'feature-gate-switch--on': featureGateSwitchValue }"
          >
            <input
              class="feature-gate-switch__input"
              type="checkbox"
              role="switch"
              v-model="featureGateSwitchValue"
              :disabled="isUpdatingCurrentFeature"
              @change="handleFeatureGateChange"
            />
            <span class="feature-gate-switch__label">
              {{ featureGateSwitchValue ? t('teacher.layout.featureGateOn') : t('teacher.layout.featureGateOff') }}
            </span>
            <span class="feature-gate-switch__thumb" aria-hidden="true"></span>
          </label>
        </div>
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import type { Component } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage } from 'element-plus';
import {
  DocumentCopy,
  Histogram,
  MoreFilled,
  Postcard,
  Promotion,
  Reading,
  Setting,
  SwitchButton,
  User,
  UserFilled,
  Warning,
} from '@element-plus/icons-vue';
import { useAuthStore } from '@/stores/auth';
import {
  getControlledPortalFeatureTarget,
  getPortalPath,
  isPortalFeatureLocked,
  isPortalMenuPathActive,
  type ControlledPortalFeatureTarget,
} from '@/router/portalRoutes';
import { FEATURE_GATE_SYNC_EVENT_KEY, useFeatureGateStore } from '@/stores/featureGate';
import expoHallLogo from '@/assets/expo-hall-logo.png';

const FEATURE_GATE_POLLING_INTERVAL_MS = 5000;

const route = useRoute();
const authStore = useAuthStore();
const { t, locale } = useI18n();
const featureGateStore = useFeatureGateStore();

interface MenuItem {
  path: string;
  labelKey: string;
  icon: Component;
  roles?: Array<'sales' | 'admin' | 'super_admin'>;
}

const menuItemsConfig: Array<Omit<MenuItem, 'path'> & { target: 'dashboard' | 'leads' | 'manualCallbacks' | 'knowledgeBase' | 'systemPrompt' | 'userManagement' | 'systemSettings' }> = [
  { target: 'dashboard', labelKey: 'teacher.layout.menu.dashboard', icon: Histogram },
  { target: 'leads', labelKey: 'teacher.layout.menu.leads', icon: DocumentCopy },
  { target: 'manualCallbacks', labelKey: 'teacher.layout.menu.manualCallbacks', icon: Warning },
  { target: 'knowledgeBase', labelKey: 'teacher.layout.menu.knowledgeBase', icon: Reading, roles: ['sales', 'admin'] },
  { target: 'systemPrompt', labelKey: 'teacher.layout.menu.systemPrompt', icon: Postcard, roles: ['admin', 'super_admin'] },
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

const currentUserRoleLabel = computed(() => {
  if (authStore.userRole === 'super_admin') return t('teacher.layout.userRoleSuper');
  if (authStore.userRole === 'admin') return t('teacher.layout.userRoleAdmin');
  return t('teacher.layout.userRole');
});

const currentAccountValue = computed(() =>
  authStore.user?.phone || authStore.user?.email || '--'
);
const profileDialogVisible = ref(false);

const isActive = (path: string) => isPortalMenuPathActive(route.path, path);
const currentFeatureGateTarget = computed<ControlledPortalFeatureTarget | null>(() =>
  getControlledPortalFeatureTarget(authStore.userRole, route.path),
);
const currentFeatureGateLabel = computed(() =>
  currentFeatureGateTarget.value ? t(`teacher.layout.menu.${featureGateTargetToLabelKey(currentFeatureGateTarget.value)}`) : '',
);
const showFeatureGateControl = computed(() =>
  authStore.userRole === 'super_admin' && !!currentFeatureGateTarget.value,
);
const isCurrentFeatureEnabled = computed(() => {
  const target = currentFeatureGateTarget.value;
  if (!target) {
    return true;
  }
  if (optimisticFeatureGateEnabled.value !== null && featureGateStore.updatingModule === target) {
    return optimisticFeatureGateEnabled.value;
  }
  return featureGateStore.modules[target] !== false;
});
const isUpdatingCurrentFeature = computed(() =>
  featureGateStore.updatingModule === currentFeatureGateTarget.value,
);
const isFeatureLocked = computed(() =>
  isPortalFeatureLocked(authStore.userRole, route.path, featureGateStore.modules),
);
let featureGatePollingTimer: number | null = null;
const optimisticFeatureGateEnabled = ref<boolean | null>(null);
const featureGateSwitchValue = ref(true);

function featureGateTargetToLabelKey(target: ControlledPortalFeatureTarget) {
  switch (target) {
    case 'manualCallbacks':
      return 'manualCallbacks';
    case 'systemPrompt':
      return 'systemPrompt';
    case 'userManagement':
      return 'userMgmt';
    case 'systemSettings':
      return 'systemSettings';
  }
}

const handleFeatureGateChange = async (event?: Event) => {
  const target = currentFeatureGateTarget.value;
  if (!target) {
    return;
  }
  const currentEnabled = featureGateStore.modules[target] !== false;
  const nextEnabled = event?.target instanceof HTMLInputElement
    ? event.target.checked
    : featureGateSwitchValue.value;
  try {
    optimisticFeatureGateEnabled.value = nextEnabled;
    featureGateSwitchValue.value = nextEnabled;
    await featureGateStore.setFeatureGate(target, nextEnabled);
    await ensureFeatureGatesLoaded(true);
    ElMessage.success(
      nextEnabled
        ? t('teacher.layout.featureGateEnableSuccess', { module: currentFeatureGateLabel.value })
        : t('teacher.layout.featureGateDisableSuccess', { module: currentFeatureGateLabel.value }),
    );
  } catch (error) {
    console.error(error);
    featureGateSwitchValue.value = currentEnabled;
    ElMessage.error(t('teacher.layout.featureGateUpdateError'));
  } finally {
    optimisticFeatureGateEnabled.value = null;
  }
};

const handleLogout = () => {
  authStore.logout();
};

const handleAccountMenuCommand = (command: string | number | object) => {
  if (command === 'profile') {
    profileDialogVisible.value = true;
  }
};

const toggleLanguage = () => {
  locale.value = locale.value === 'zh-CN' ? 'en' : 'zh-CN';
  localStorage.setItem('selectedLanguage', locale.value);
};

const ensureFeatureGatesLoaded = async (force = false) => {
  if (!authStore.userRole) {
    return;
  }
  try {
    await featureGateStore.fetchFeatureGates(force);
  } catch (error) {
    console.error('Failed to load feature gates:', error);
  }
};

const handleFeatureGateStorageSync = (event: StorageEvent) => {
  if (event.key !== FEATURE_GATE_SYNC_EVENT_KEY) {
    return;
  }
  void ensureFeatureGatesLoaded(true);
};

const handleFeatureGateVisibilitySync = () => {
  if (document.hidden) {
    return;
  }
  void ensureFeatureGatesLoaded(true);
};

const startFeatureGatePolling = () => {
  if (featureGatePollingTimer !== null) {
    window.clearInterval(featureGatePollingTimer);
  }
  featureGatePollingTimer = window.setInterval(() => {
    if (document.hidden || !authStore.userRole) {
      return;
    }
    void ensureFeatureGatesLoaded(true);
  }, FEATURE_GATE_POLLING_INTERVAL_MS);
};

const stopFeatureGatePolling = () => {
  if (featureGatePollingTimer === null) {
    return;
  }
  window.clearInterval(featureGatePollingTimer);
  featureGatePollingTimer = null;
};

onMounted(() => {
  void ensureFeatureGatesLoaded(true);
  startFeatureGatePolling();
  window.addEventListener('storage', handleFeatureGateStorageSync);
  window.addEventListener('focus', handleFeatureGateVisibilitySync);
  document.addEventListener('visibilitychange', handleFeatureGateVisibilitySync);
});

watch(
  () => authStore.userRole,
  () => {
    void ensureFeatureGatesLoaded(true);
  },
);

watch(
  () => route.path,
  () => {
    void ensureFeatureGatesLoaded(true);
  },
);

watch(
  () => [currentFeatureGateTarget.value, isCurrentFeatureEnabled.value, featureGateStore.updatingModule] as const,
  ([target, enabled, updatingModule]) => {
    if (!target) {
      featureGateSwitchValue.value = true;
      return;
    }
    if (updatingModule === target && optimisticFeatureGateEnabled.value !== null) {
      featureGateSwitchValue.value = optimisticFeatureGateEnabled.value;
      return;
    }
    featureGateSwitchValue.value = enabled;
  },
  { immediate: true },
);

onUnmounted(() => {
  stopFeatureGatePolling();
  window.removeEventListener('storage', handleFeatureGateStorageSync);
  window.removeEventListener('focus', handleFeatureGateVisibilitySync);
  document.removeEventListener('visibilitychange', handleFeatureGateVisibilitySync);
});
</script>

<style scoped>
.teacher-layout {
  position: relative;
  display: flex;
  min-height: 100vh;
  overflow: hidden;
  background: #ffffff;
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  display: flex;
  width: 320px;
  flex-direction: column;
  border-right: 1px solid #e8edf3;
  background: #ffffff;
  box-shadow: none;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 22px 34px 16px;
}

.sidebar-divider {
  height: 1px;
  margin: 0 22px 8px;
  background: #edf0f4;
}

.brand-mark {
  display: grid;
  width: 92px;
  height: 68px;
  place-items: center;
  flex-shrink: 0;
}

.brand-logo {
  display: block;
  width: 92px;
  height: 68px;
  object-fit: contain;
}

.brand-copy {
  min-width: 0;
}

.logo-title {
  color: #273142;
  font-size: 21px;
  font-weight: 800;
  line-height: 1.2;
}

.logo-subtitle {
  margin-top: 4px;
  color: #7a8595;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
}

.nav-menu {
  flex: 1;
  padding: 6px 18px 18px 12px;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 18px;
  min-height: 64px;
  margin-bottom: 8px;
  padding: 0 22px 0 28px;
  border-radius: 14px;
  color: #6c7c92;
  text-decoration: none;
  transition:
    background-color 0.22s ease,
    color 0.22s ease,
    transform 0.22s ease;
}

.nav-item:hover {
  background: #f5f7fa;
  color: #2d3646;
  transform: none;
}

.nav-item.active {
  background: #eef3f9;
  color: #243041;
  border: 1px solid #dde5ef;
}

.nav-active-bar {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 8px;
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
  font-size: 30px;
}

.nav-label {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0 24px 10px;
  padding: 18px 0 0;
  font-family: SimSun, "Songti SC", "STSong", serif;
}

.footer-action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid #edf0f4;
}

.language-btn,
.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 50px;
  border: none;
  border-radius: 12px;
  background: transparent;
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
.language-btn:active {
  background: #f5f7fa;
  transform: translateY(-1px);
}

.language-icon,
.logout-icon {
  font-size: 18px;
}

.logout-btn:hover,
.logout-btn:active {
  background: #fbe5e3;
  color: #c4473a;
  transform: translateY(-1px);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
  min-height: 72px;
  border-radius: 16px;
  margin-top: 8px;
  transition: background-color 0.22s ease, box-shadow 0.22s ease;
}

.user-info:hover {
  background: #f2f5f8;
}

.user-avatar {
  display: grid;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  place-items: center;
  border-radius: 50%;
  background: #f0f2f5;
  color: #506177;
  font-size: 21px;
}

.user-details {
  min-width: 0;
  flex: 1;
}

.user-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  min-height: 26px;
}

.user-name {
  min-width: 0;
  flex: 0 1 auto;
  color: #283141;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  flex: 1;
  min-width: 0;
  color: #8691a0;
  font-size: 12px;
  font-weight: 650;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-more-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  align-self: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #98a3b2;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.account-more-btn:hover {
  background: #f3f6fa;
  color: #2d3646;
}

:deep(.account-more-btn svg) {
  display: block;
}

:deep(.account-dropdown-menu) {
  min-width: 164px;
  padding: 8px;
  border-radius: 18px;
  border: 1px solid #e4e9f0;
  background: #ffffff;
  box-shadow: 0 22px 44px rgba(31, 44, 61, 0.14);
}

:deep(.account-dropdown-menu .el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  border-radius: 14px;
  color: #2d3646;
  font-size: 15px;
  font-weight: 700;
}

:deep(.account-dropdown-menu .el-dropdown-menu__item:not(.is-disabled):hover) {
  background: #f1f4f7;
  color: #243041;
}

:deep(.profile-dialog-mask) {
  background: rgba(15, 23, 42, 0.2);
  backdrop-filter: blur(8px);
}

:deep(.profile-dialog .el-dialog) {
  border: 1px solid #e8edf3;
  border-radius: 24px;
  padding: 4px;
  opacity: 1;
  background: #ffffff;
  box-shadow: 0 26px 60px rgba(15, 23, 42, 0.16);
}

:deep(.profile-dialog .el-dialog__header) {
  padding: 22px 26px 10px;
  background: #ffffff;
}

:deep(.profile-dialog .el-dialog__title) {
  color: #243041;
  font-size: 28px;
  font-weight: 800;
}

:deep(.profile-dialog .el-dialog__headerbtn) {
  top: 22px;
  right: 24px;
}

:deep(.profile-dialog .el-dialog__close) {
  color: #8d98a8;
  font-size: 20px;
}

:deep(.profile-dialog .el-dialog__body) {
  padding: 8px 26px 28px;
  background: #ffffff;
}

.profile-dialog-body {
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 40px;
  align-items: start;
  background: #ffffff;
}

.profile-side-nav {
  padding-top: 6px;
  background: #ffffff;
}

.profile-side-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 54px;
  padding: 0 16px;
  border: 1px solid #e3e8ef;
  border-radius: 16px;
  background: #f3f6fa;
  color: #243041;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.22s ease, border-color 0.22s ease;
}

.profile-side-item:hover,
.profile-side-item--active {
  border-color: #d7e0ea;
  background: #eef3f8;
}

.profile-content {
  min-width: 0;
  background: #ffffff;
}

.profile-info-table {
  border: none;
  border-radius: 0;
  overflow: visible;
  background: #ffffff;
}

.profile-info-row {
  display: grid;
  grid-template-columns: 112px 1fr;
  gap: 24px;
  min-height: 88px;
  align-items: center;
  padding: 0 8px 0 0;
  border-bottom: 1px solid #e7edf4;
}

.profile-info-row:last-child {
  border-bottom: none;
}

.profile-info-label {
  color: #1f2937;
  font-size: 16px;
  font-weight: 500;
}

.profile-info-value {
  color: #243041;
  font-size: 16px;
  font-weight: 500;
  word-break: break-all;
}

.main-wrapper {
  flex: 1;
  min-height: 100vh;
  margin-left: 320px;
  border-left: 1px solid #e9edf2;
  background: #f7f9fc;
}

.content-area {
  position: relative;
  z-index: 10;
  min-height: 100vh;
  padding: 18px 22px;
}

.feature-gate-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
  padding: 16px 18px;
  border: 1px solid rgba(207, 216, 228, 0.95);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 14px 30px rgba(31, 44, 61, 0.08);
}

.feature-gate-copy {
  min-width: 0;
}

.feature-gate-title {
  color: #223145;
  font-size: 16px;
  font-weight: 800;
}

.feature-gate-desc {
  margin-top: 4px;
  color: #748196;
  font-size: 13px;
  font-weight: 600;
}

.feature-gate-switch {
  position: relative;
  display: inline-flex;
  min-width: 86px;
  height: 34px;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 8px 0 13px;
  border: 1px solid #cfd8e4;
  border-radius: 999px;
  background: #f4f6f9;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, opacity 0.18s ease;
}

.feature-gate-switch--on {
  border-color: #1e8df2;
  background: #2f95f4;
  color: #ffffff;
}

.feature-gate-switch:disabled {
  cursor: wait;
  opacity: 0.65;
}

.feature-gate-switch__input {
  position: absolute;
  inset: 0;
  z-index: 2;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.feature-gate-switch__input:disabled {
  cursor: wait;
}

.feature-gate-switch__label,
.feature-gate-switch__thumb {
  position: relative;
  z-index: 1;
}

.feature-gate-switch__thumb {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.18);
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
    width: 272px;
  }

  .main-wrapper {
    margin-left: 272px;
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
    border-radius: 12px;
  }

  .sidebar-footer {
    margin: 0 10px 14px;
    padding: 12px 0 0;
  }

  .user-info {
    justify-content: center;
    padding: 12px 10px;
  }

  .footer-action-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .main-wrapper {
    margin-left: 94px;
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 78px;
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
    min-height: 44px;
  }

  .user-avatar {
    width: 42px;
    height: 42px;
    font-size: 20px;
  }

  .main-wrapper {
    margin-left: 78px;
  }

  .content-area {
    padding: 10px;
  }

  .feature-gate-control {
    align-items: flex-start;
    flex-direction: column;
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

  .profile-dialog-body {
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .profile-info-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
</style>
