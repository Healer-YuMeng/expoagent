/**
 * Axios 请求封装
 */
import axios from 'axios';
import type { AxiosInstance, AxiosResponse } from 'axios';
import { useAuthStore } from '@/stores/auth';

const request: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore();
    const rawUrl = config.url ?? '';
    const normalizedUrl = rawUrl.startsWith('http')
      ? new URL(rawUrl).pathname
      : rawUrl;
    const isParentApi = normalizedUrl.startsWith('/v1/parent') || normalizedUrl.startsWith('/api/v1/parent');
    const bearerToken = isParentApi ? authStore.getParentAccessToken() : authStore.token;

    if (bearerToken) {
      config.headers.Authorization = `Bearer ${bearerToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data;
  },
  (error) => {
    if (error.response) {
      const { status } = error.response;
      if (status === 401) {
        const authStore = useAuthStore();
        const rawUrl = error.config?.url ?? '';
        const normalizedUrl = rawUrl.startsWith('http')
          ? new URL(rawUrl).pathname
          : rawUrl;
        const isParentApi = normalizedUrl.startsWith('/v1/parent') || normalizedUrl.startsWith('/api/v1/parent');

        if (isParentApi) {
          authStore.clearParentAuth(); // 家长访客身份失效，清除家长侧凭据，稍后重新初始化
        } else {
          authStore.logout(); // 老师端等需要重新登录
        }
      }
    }
    return Promise.reject(error);
  }
);

export default request;
