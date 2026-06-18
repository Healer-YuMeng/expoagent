/**
 * 认证相关 API
 */
import request from '@/utils/request';
import type { LoginRequest, LoginResponse, User, AnonymousSessionResponse } from '@/types';

/**
 * 用户登录
 */
export function login(data: LoginRequest): Promise<LoginResponse> {
  return request.post('/v1/auth/login', data);
}

/**
 * 创建或恢复匿名访客会话
 */
export function createAnonymousSession(payload?: { anonymous_id?: string }): Promise<AnonymousSessionResponse> {
  return request.post('/v1/auth/anonymous-session', payload ?? {});
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser(): Promise<User> {
  return request.get('/v1/auth/me');
}

/**
 * 登出
 */
export function logout(): Promise<{ message: string }> {
  return request.post('/v1/auth/logout');
}
