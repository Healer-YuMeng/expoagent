import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as loginApi, createAnonymousSession } from '@/api/auth';
import type { User, LoginRequest, AnonymousSessionResponse } from '@/types';
import router from '@/router';
import { getAppStorageItem, removeAppStorageItem, setAppStorageItem } from '@/utils/browserStorage';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('ycis_token'));
  const user = ref<User | null>(JSON.parse(localStorage.getItem('ycis_user') || 'null'));
  const parentToken = ref<string | null>(getAppStorageItem('ycis_parent_token'));
  const parentUser = ref<User | null>(JSON.parse(getAppStorageItem('ycis_parent_user') || 'null'));
  const anonymousId = ref<string | null>(getAppStorageItem('ycis_anonymous_id'));

  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const userRole = computed(() => user.value?.role);

  function setAuth(t: string, u: User) {
    token.value = t;
    user.value = u;
    localStorage.setItem('ycis_token', t);
    localStorage.setItem('ycis_user', JSON.stringify(u));
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
    localStorage.removeItem('ycis_token');
    localStorage.removeItem('ycis_user');
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

  async function login(credentials: LoginRequest) {
    try {
      const response = await loginApi(credentials);
      setAuth(response.access_token, response.user);
      
      // 根据角色跳转到不同页面
      if (response.user.role === 'teacher' || response.user.role === 'school_admin' || response.user.role === 'super_admin') {
        router.push({ name: 'Dashboard' });
      } else {
        router.push('/parent/conversations');
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
    router.push('/auth/login');
  }

  return {
    token,
    user,
    parentToken,
    parentUser,
    anonymousId,
    isAuthenticated,
    userRole,
    login,
    initializeAnonymousSession,
    ensureParentSession,
    getParentAccessToken,
    logout,
    clearAuth,
    clearParentAuth,
  };
});
