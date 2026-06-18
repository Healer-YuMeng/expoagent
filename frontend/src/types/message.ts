export interface Message {
  id: string;
  conversation_id: string;
  sender_type: 'parent' | 'bot' | 'teacher';
  sender_id?: string;
  sender_name?: string;
  content: string;
  created_at: string;
}
