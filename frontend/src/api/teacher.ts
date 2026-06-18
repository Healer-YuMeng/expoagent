/**
 * 老师工作台相关 API
 */
import request from '@/utils/request';
import type { ManualCallbackItem } from '@/types';
import type { Message } from '@/types/message';

export interface ChannelMetricEntry {
  channel: string;
  label: string;
  visits: number;
  appointments: number;
}

export interface DashboardStats {
  today_consultations: number;
  valid_leads: number;
  urgent_followups: number;
  pending_appointments: number;
  manual_callbacks: number;
  source_stats?: Record<'daily' | 'monthly' | 'yearly', ChannelMetricEntry[]>;
}

export interface WelcomeMessageResponse {
  messages: Record<string, string>; // key: 语言代码, value: 欢迎语内容
}

export interface TranslateRequest {
  source_text: string;
  source_lang?: string;
}

export interface TranslateResponse {
  translations: Record<string, string>; // key: 语言代码, value: 翻译后的文本
  failed_languages?: string[];
}

/**
 * 获取老师工作台摘要数据
 */
export function getTeacherDashboard(): Promise<DashboardStats> {
  return request.get('/v1/teacher/dashboard');
}

export function getWelcomeMessage(): Promise<WelcomeMessageResponse> {
  return request.get('/v1/teacher/settings/welcome-message');
}

export function updateWelcomeMessage(data: { messages: Record<string, string> }): Promise<WelcomeMessageResponse> {
  return request.put('/v1/teacher/settings/welcome-message', data);
}

export function translateWelcomeMessage(data: TranslateRequest): Promise<TranslateResponse> {
  return request.post('/v1/teacher/settings/welcome-message/translate', data, {
    timeout: 120000,
  });
}

export function getManualCallbacks(): Promise<{ items: ManualCallbackItem[] }> {
  return request.get('/v1/teacher/manual-callbacks');
}

export function deleteManualCallback(conversationId: string): Promise<{ message: string }> {
  return request.delete(`/v1/teacher/manual-callbacks/${conversationId}`);
}

export function getTeacherConversationMessages(
  conversationId: string,
  params?: { page?: number; page_size?: number }
): Promise<{ items: Message[]; total: number; ai_reply_enabled: boolean }> {
  return request.get(`/v1/teacher/conversations/${conversationId}/messages`, { params });
}

export function sendTeacherConversationMessage(
  conversationId: string,
  data: { content: string },
): Promise<Message> {
  return request.post(`/v1/teacher/conversations/${conversationId}/messages`, data);
}

export function updateTeacherConversationAiReply(
  conversationId: string,
  enabled: boolean,
): Promise<{ conversation_id: string; ai_reply_enabled: boolean }> {
  return request.patch(`/v1/teacher/conversations/${conversationId}/ai-reply`, { enabled });
}

// --------- 系统提示词 ---------
export interface PromptResponse {
  key: string;
  content: string;
  locale?: string | null;
  school_id?: string | null;
  assistant_id?: string | null;
  version?: number | null;
  updated_at?: string | null;
  updated_by?: string | null;
  is_default: boolean;
  default_content?: string | null;
}

export interface AssistantItem {
  id: string;
  name: string;
  school_id: string;
  admin_id?: string | null;
  knowledge_base_id?: string | null;
  is_active: boolean;
}

export interface KnowledgeBaseItem {
  id: string;
  name: string;
  description?: string | null;
  doc_count?: number;
}

export function getSystemPrompt(locale?: string | null, school_id?: string | null, assistant_id?: string | null): Promise<PromptResponse> {
  return request.get('/v1/prompts/assistant_system_prompt', {
    params: { locale: locale || undefined, school_id: school_id || undefined, assistant_id: assistant_id || undefined },
  });
}

export function updateSystemPrompt(data: { content: string; locale?: string | null; school_id?: string | null; assistant_id?: string | null }): Promise<PromptResponse> {
  return request.put('/v1/prompts/assistant_system_prompt', data);
}

export function listAssistants(school_id?: string | null): Promise<{ items: AssistantItem[] }> {
  return request.get('/v1/assistants', {
    params: { school_id: school_id || undefined },
  });
}

export function createAssistant(data: { name: string; school_id?: string | null }): Promise<AssistantItem> {
  return request.post('/v1/assistants', data);
}

export function updateAssistant(
  assistantId: string,
  data: { name?: string; knowledge_base_id?: string | null; is_active?: boolean },
): Promise<AssistantItem> {
  return request.patch(`/v1/assistants/${assistantId}`, data);
}

export function listKnowledgeBases(school_id?: string | null): Promise<{ items: KnowledgeBaseItem[] }> {
  return request.get('/v1/docs/knowledge-bases', {
    params: { school_id: school_id || undefined },
  });
}

// --------- 账户管理 ---------
export interface ManagedUser {
  id: string;
  phone: string;
  role: 'teacher' | 'school_admin';
  name?: string;
  email?: string;
  is_active?: boolean;
  school_id?: string | null;
  school_name?: string | null;
  admin_id?: string | null;
}

export function listManagedUsers(role?: string): Promise<{ items: ManagedUser[] }> {
  return request.get('/v1/users', { params: role ? { role } : undefined });
}

export function createManagedUser(payload: {
  phone: string;
  password: string;
  role: 'teacher' | 'school_admin';
  name?: string;
  email?: string;
  school_id?: string | null;
  school_name?: string | null;
}): Promise<ManagedUser> {
  return request.post('/v1/users', payload);
}

export function deleteManagedUser(userId: string): Promise<{ message: string }> {
  return request.delete(`/v1/users/${userId}`);
}
