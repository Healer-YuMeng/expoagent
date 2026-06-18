export interface User {
  id: string;
  phone: string;
  name: string;
  role: 'parent' | 'teacher' | 'school_admin' | 'super_admin';
  email?: string;
  is_active: boolean;
  created_at: string;
  school_id?: string | null;
  school_name?: string | null;
  admin_id?: string | null;
}

export interface LoginRequest {
  phone: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AnonymousSessionResponse extends LoginResponse {
  anonymous_id: string;
}

export type WecomStatus = 'not_added' | 'pending' | 'added';

export interface FollowUpOwner {
  name: string;
  campus?: string;
  wechat_id?: string;
  qr_code_url?: string;
  contact_phone?: string;
}

export interface WecomChatMessage {
  id: string;
  external_userid?: string;
  direction: 'parent' | 'teacher' | 'bot';
  content: string;
  sent_at?: string | null;
}

export interface PaginatedLeads {
  total: number;
  items: LeadListItem[];
  page: number;
  page_size: number;
}

export interface AppointmentInfo {
  status: 'pending' | 'confirmed' | 'rejected';
  campus?: string | null;
  timeslot: string;
  parent_name?: string | null;
  guardian_name?: string | null;
  phone?: string | null;
  email?: string | null;
  note?: string | null;
}

export interface FollowUpNoteItem {
  id?: string;
  content: string;
  follow_up_method?: string | null;
  created_by?: string | null;
  created_by_name?: string | null;
  created_at?: string | null;
}

export interface LeadListItem {
  id: string;
  parent_name: string;
  parent_phone?: string;
  display_name?: string;
  display_phone?: string;
  campus?: string;
  is_high_intent: boolean;
  needs_manual_callback: boolean;
  source?: string;
  intent_score: number;
  tags: string[];
  summary?: string;
  en_summary?: string;
  extracted_info?: Record<string, unknown>;
  notes_count?: number;
  next_follow_up_date?: string | null;
  created_at: string;
  updated_at?: string | null;
  appointment_status?: string | null;
  appointment_timeslot?: string | null;
  appointment?: AppointmentInfo | null;
  follow_up_owner?: FollowUpOwner | null;
  wecom_status?: WecomStatus;
  wecom_contact_name?: string | null;
}

export interface Lead extends LeadListItem {
  parent_email?: string;
  conversation_id: string | null;
  extracted_info: Record<string, unknown>;
  notes: FollowUpNoteItem[];
  appointment?: AppointmentInfo | null;
  first_message_at?: string | null;
  wecom_chat_history?: WecomChatMessage[];
  wecom_contact_id?: string | null;
}

export interface ManualCallbackItem {
  conversation_id: string;
  reason: string;
  query: string;
  parent_name?: string | null;
  parent_phone?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpdateLeadRequest {
  is_high_intent?: boolean;
  needs_manual_callback?: boolean;
  wecom_status?: WecomStatus;
  follow_up_owner?: FollowUpOwner | null;
  wecom_contact_name?: string | null;
}

export interface AddFollowUpNoteRequest {
  content: string;
  follow_up_method?: string;
}

export interface Conversation {
  id: string;
  message_count: number;
  created_at: string;
  last_message_at?: string;
  last_message_preview?: string;
  [key: string]: any;
}

export interface PaginatedConversations {
  total: number;
  items: Conversation[];
  page: number;
  page_size: number;
}
