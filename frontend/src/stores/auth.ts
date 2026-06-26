import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as loginApi, createAnonymousSession } from '@/api/auth';
import type { User, LoginRequest, AnonymousSessionResponse } from '@/types';
import { getAppStorageItem, removeAppStorageItem, setAppStorageItem } from '@/utils/browserStorage';
import { getPortalHomePath } from '@/router/portalRoutes';
import {
  isSessionExpired,
  parseSessionTimestamp,
  resolvePostLoginPath,
} from '@/utils/authSession';
import {
  clearAdminAuthStorage,
  loadAdminAuthStorage,
  persistAdminAuthStorage,
} from '@/utils/adminAuthStorage';

async function navigateTo(path: string) {
  const routerModule = await import('@/router');
  await routerModule.default.push(path);
}

export const useAuthStore = defineStore('auth', () => {
  const adminAuthSnapshot = loadAdminAuthStorage(window.sessionStorage, window.localStorage);
  const token = ref<string | null>(adminAuthSnapshot.token);
  const user = ref<User | null>(JSON.parse(adminAuthSnapshot.userJson || 'null'));
  const loginAt = ref<number | null>(parseSessionTimestamp(adminAuthSnapshot.loginAt));
  const parentToken = ref<string | null>(getAppStorageItem('ycis_parent_token'));
  const parentUser = ref<User | null>(JSON.parse(getAppStorageItem('ycis_parent_user') || 'null'));
  const anonymousId = ref<string | null>(getAppStorageItem('ycis_anonymous_id'));

  const isAuthenticated = computed(() => !!token.value && !!user.value && !isSessionExpired(loginAt.value));
  const userRole = computed(() => user.value?.role);

  function setAuth(t: string, u: User) {
    const now = Date.now();
    token.value = t;
    user.value = u;
    loginAt.value = now;
    persistAdminAuthStorage(
      window.sessionStorage,
      window.localStorage,
      t,
      JSON.stringify(u),
      now,
    );
  }

  function setParentAuth(t: string, u: User) {
    parentToken.value = t;
    parentUser.value = u;
    setAppStorageItem('ycis_parent_token', t);
    setAppStorageItem('ycis_parent_user', JSON.stringify(u));
  }

  function clearAuth() {
    token.value = null;
    user.value = null;
    loginAt.value = null;
    clearAdminAuthStorage(window.sessionStorage, window.localStorage);
  }

  function clearParentAuth() {
    parentToken.value = null;
    parentUser.value = null;
    anonymousId.value = null;
    removeAppStorageItem('ycis_parent_token');
    removeAppStorageItem('ycis_parent_user');
    removeAppStorageItem('ycis_anonymous_id');
  }

  function getParentAccessToken() {
    if (parentToken.value && parentUser.value?.role === 'parent') {
      return parentToken.value;
    }
    if (token.value && user.value?.role === 'parent') {
      return token.value;
    }
    return null;
  }

  function hasSessionExpired(now = Date.now()) {
    return !!token.value && !!user.value && isSessionExpired(loginAt.value, now);
  }

  function ensureValidSession() {
    if (!hasSessionExpired()) {
      return true;
    }
    clearAuth();
    return false;
  }

  async function login(credentials: LoginRequest, redirectPath?: string | null) {
    try {
      const response = await loginApi(credentials);
      setAuth(response.access_token, response.user);
      
      // 根据角色跳转到不同页面
      if (response.user.role === 'sales' || response.user.role === 'admin' || response.user.role === 'super_admin') {
        const fallbackPath = getPortalHomePath(response.user.role);
        await navigateTo(resolvePostLoginPath(redirectPath, fallbackPath));
      } else {
        await navigateTo('/start-chat');
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }

  async function initializeAnonymousSession(existingId?: string | null): Promise<AnonymousSessionResponse> {
    try {
      const response = await createAnonymousSession(existingId ? { anonymous_id: existingId } : undefined);
      setParentAuth(response.access_token, response.user);
      anonymousId.value = response.anonymous_id;
      setAppStorageItem('ycis_anonymous_id', response.anonymous_id);
      return response;
    } catch (error) {
      console.error('Failed to initialize anonymous session:', error);
      throw error;
    }
  }

  async function ensureParentSession(forceRefresh = false): Promise<string> {
    if (!forceRefresh) {
      const existingToken = getParentAccessToken();
      if (existingToken) {
        return existingToken;
      }
    }

    const response = await initializeAnonymousSession(forceRefresh ? undefined : anonymousId.value);
    return response.access_token;
  }

  function logout() {
    clearAuth();
    void navigateTo('/auth/login');
  }

  if (token.value && user.value) {
    ensureValidSession();
  }

  return {
    token,
    user,
    loginAt,
    parentToken,
    parentUser,
    anonymousId,
    isAuthenticated,
    userRole,
    hasSessionExpired,
    ensureValidSession,
    login,
    initializeAnonymousSession,
    ensureParentSession,
    getParentAccessToken,
    logout,
    clearAuth,
    clearParentAuth,
  };
});
