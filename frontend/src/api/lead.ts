/**
 * 线索相关 API
 */
import request from '@/utils/request';
import type {
  Lead,
  PaginatedLeads,
  UpdateLeadRequest,
  AddFollowUpNoteRequest,
  WecomStatus,
} from '@/types';

export interface UpdateFollowUpNoteRequest {
  content: string;
  follow_up_method?: string;
}

// 假设的类型定义，后续应在 types/index.ts 中完善
export interface LeadFilters {
  page?: number;
  page_size?: number;
  high_intent_only?: boolean;
  manual_callback_only?: boolean;
  search?: string;
  language?: string;
  tags?: string[];
  date?: string; // YYYY-MM-DD
  appointment_status?: string;
  wecom_status?: WecomStatus;
}

/**
 * 获取线索列表 (管理员/老师)
 */
export function getLeads(params: LeadFilters): Promise<PaginatedLeads> {
  return request.get('/v1/leads', { params });
}

/**
 * 导出线索为 Excel
 */
export function exportLeads(params: LeadFilters): Promise<Blob> {
  return request.get('/v1/leads/export', { params, responseType: 'blob' as any });
}

/**
 * 获取线索详情
 */
export function getLead(id: string, language?: string): Promise<Lead> {
  return request.get(`/v1/leads/${id}`, {
    params: language ? { language } : undefined,
  });
}

/**
 * 更新线索
 */
export function updateLead(id: string, data: UpdateLeadRequest): Promise<Lead> {
  return request.put(`/v1/leads/${id}`, data);
}

/**
 * 添加跟进记录
 */
export function addFollowUpNote(
  id: string,
  data: AddFollowUpNoteRequest
): Promise<{ message: string }> {
  return request.post(`/v1/leads/${id}/notes`, data);
}

/**
 * 更新跟进记录
 */
export function updateFollowUpNote(
  leadId: string,
  noteId: string,
  data: UpdateFollowUpNoteRequest
): Promise<{ message: string }> {
  return request.put(`/v1/leads/${leadId}/notes/${noteId}`, data);
}

/**
 * 删除跟进记录
 */
export function deleteFollowUpNote(
  leadId: string,
  noteId: string
): Promise<{ message: string }> {
  return request.delete(`/v1/leads/${leadId}/notes/${noteId}`);
}

/**
 * 删除线索（软删除，标记为流失）
 */
export function deleteLead(id: string): Promise<{ message: string }> {
  return request.delete(`/v1/leads/${id}`);
}
