/**
 * 会话相关 API
 */
import request from '@/utils/request';
import type { Message } from '@/types/message';
import type { Conversation, PaginatedConversations } from '@/types'; // Assuming these types exist
import { useAuthStore } from '@/stores/auth';

export interface ParentAssistantItem {
  id: string;
  name: string;
  school_id: string;
  knowledge_base_id?: string | null;
  is_active: boolean;
}

// --- Parent Endpoints ---

/**
 * 获取我的会话列表 (家长)
 */
export function getMyConversations(params?: { page?: number; page_size?: number }): Promise<PaginatedConversations> {
  return request.get('/v1/parent/conversations', { params });
}

/**
 * 创建新会话 (家长)
 */
export function createConversation(payload?: { language?: string; source?: string | null; school_id?: string | null; assistant_id?: string | null }): Promise<Conversation> {
  return request.post('/v1/parent/conversations', payload);
}

/**
 * 获取单个会话的消息列表 (家长)
 */
export function getParentConversationMessages(
  conversationId: string,
  params?: { page?: number; page_size?: number; language?: string; school_id?: string | null }
): Promise<{ items: Message[]; total: number }> {
  return request.get(`/v1/parent/conversations/${conversationId}/messages`, { params });
}

export function getParentWelcomeMessage(
  conversationId: string,
  language: string,
  schoolId?: string | null
): Promise<{ language: string; content: string }> {
  return request.get(`/v1/parent/conversations/${conversationId}/welcome-message`, {
    params: {
      language,
      school_id: schoolId || undefined,
    },
  });
}

export function listParentAssistants(params?: {
  school_id?: string | null;
  conversation_id?: string | null;
}): Promise<{
  items: ParentAssistantItem[];
  selected_assistant_id?: string | null;
  school_id?: string | null;
}> {
  return request.get('/v1/parent/assistants', {
    params: {
      school_id: params?.school_id || undefined,
      conversation_id: params?.conversation_id || undefined,
    },
  });
}

export function updateConversationAssistant(
  conversationId: string,
  assistantId: string,
): Promise<Conversation> {
  return request.patch(`/v1/parent/conversations/${conversationId}/assistant`, {
    assistant_id: assistantId,
  });
}

/**
 * 发送消息（流式）
 * This uses fetch directly to handle streaming response.
 */
export async function sendMessage(
  conversationId: string,
  content: string,
  language: string,
  schoolId: string | null | undefined,
  assistantId: string | null | undefined,
  onChunk: (chunk: string) => void
) {
  const authStore = useAuthStore();
  const token = authStore.getParentAccessToken();
  const controller = new AbortController();
  const response = await fetch(`/api/v1/parent/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token || ''}`,
    },
    body: JSON.stringify({ content, language, school_id: schoolId || undefined, assistant_id: assistantId || undefined }),
    signal: controller.signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let shouldStop = false;
    const events = buffer.split('\n\n');
    buffer = events.pop() || '';

    for (const rawEvent of events) {
      const lines = rawEvent
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.startsWith('data: '));

      for (const line of lines) {
        const data = line.slice(6);
        onChunk(data);
        try {
          const parsed = JSON.parse(data);
          if (parsed.event === 'done') {
            shouldStop = true;
          }
        } catch (e) {
          // ignore parse errors
        }
      }
    }

    if (shouldStop) {
      reader.cancel();
      controller.abort();
      break;
    }
  }
}


// --- Admin/Teacher Endpoints ---

/**
 * 获取会话消息列表 (管理员/老师)
 */
export function getAdminConversationMessages(
  conversationId: string,
  params?: { page?: number; page_size?: number }
): Promise<{ items: Message[]; total: number }> {
  return request.get(`/v1/admin/conversations/${conversationId}/messages`, { params });
}
