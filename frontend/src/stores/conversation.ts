import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { AxiosError } from 'axios';
import {
  getMyConversations,
  createConversation as createConversationApi,
  getParentConversationMessages,
  sendMessage as sendMessageApi
} from '@/api/conversation';
import type { Conversation } from '@/types';
import type { Message } from '@/types/message';
import { useAuthStore } from '@/stores/auth';
import { getPersistedChannelSource } from '@/utils/channelSource';
import { persistLastParentConversationId } from '@/utils/parentConversation';
import { getAppStorageItem } from '@/utils/browserStorage';

export const useConversationStore = defineStore('conversation', () => {

  const conversations = ref<Conversation[]>([]);
  const currentMessages = ref<Message[]>([]);
  const loading = ref(false);
  const loadingMessages = ref(false);

  async function ensureParentSession(reset = false) {
    const authStore = useAuthStore();
    await authStore.ensureParentSession(reset);
  }

  function isAuthError(error: unknown) {
    const axiosError = error as AxiosError;
    const status = axiosError?.response?.status;
    return status === 401 || status === 403;
  }

  async function fetchConversations() {
    loading.value = true;
    try {
      await ensureParentSession();
      const response = await getMyConversations({ page: 1, page_size: 50 });
      conversations.value = response.items;
    } catch (error) {
      if (isAuthError(error)) {
        try {
          await ensureParentSession(true);
          const response = await getMyConversations({ page: 1, page_size: 50 });
          conversations.value = response.items;
          return;
        } catch (retryError) {
          console.error("Failed to fetch conversations after retry:", retryError);
        }
      } else {
        console.error("Failed to fetch conversations:", error);
      }
    } finally {
      loading.value = false;
    }
  }

  async function fetchMessages(conversationId: string) {
    loadingMessages.value = true;
    const selectedLanguage = getAppStorageItem('selectedLanguage') || 'zh-CN';
    try {
      await ensureParentSession();
      const response = await getParentConversationMessages(conversationId, {
        page: 1,
        page_size: 200,
        language: selectedLanguage,
      });
      currentMessages.value = response.items;
      persistLastParentConversationId(conversationId);
    } catch (error) {
      if (isAuthError(error)) {
        try {
          await ensureParentSession(true);
          const response = await getParentConversationMessages(conversationId, {
            page: 1,
            page_size: 200,
            language: selectedLanguage,
          });
          currentMessages.value = response.items;
          persistLastParentConversationId(conversationId);
          return;
        } catch (retryError) {
          console.error("Failed to fetch messages after retry:", retryError);
        }
      } else {
        console.error("Failed to fetch messages:", error);
      }
      currentMessages.value = [];
    } finally {
      loadingMessages.value = false;
    }
  }

  async function createNewConversation() {
    const createConversation = async () => {
      const selectedLanguage = getAppStorageItem('selectedLanguage') || 'zh-CN';
      const source = getPersistedChannelSource();
      const assistantId = getAppStorageItem('selectedAssistantId') || '';
      const newConversation = await createConversationApi({
        language: selectedLanguage,
        source,
        assistant_id: assistantId || undefined,
      });
      conversations.value.unshift(newConversation);
      persistLastParentConversationId(newConversation.id);
      return newConversation;
    };

    try {
      await ensureParentSession();
      return await createConversation();
    } catch (error) {
      if (isAuthError(error)) {
        await ensureParentSession(true);
        return await createConversation();
      }
      console.error("Failed to create conversation:", error);
      throw error;
    }
  }

  async function postMessage(conversationId: string, content: string) {
    const selectedLanguage = getAppStorageItem('selectedLanguage') || 'zh-CN';
    const assistantId = getAppStorageItem('selectedAssistantId') || '';
    const userMessage: Message = {
      id: Date.now().toString(),
      conversation_id: conversationId,
      sender_type: 'parent',
      content,
      created_at: new Date().toISOString(),
    };
    currentMessages.value.push(userMessage);

    const botMessage: Message = {
      id: (Date.now() + 1).toString(),
      conversation_id: conversationId,
      sender_type: 'bot',
      content: '',
      created_at: new Date().toISOString(),
    };
    let botMessageVisible = false;
    let botPlaceholderTimer: number | null = window.setTimeout(() => {
      if (botMessageVisible) {
        return;
      }
      botMessageVisible = true;
      currentMessages.value.push(botMessage);
      currentMessages.value = [...currentMessages.value];
    }, 250);

    const clearBotPlaceholderTimer = () => {
      if (botPlaceholderTimer !== null) {
        window.clearTimeout(botPlaceholderTimer);
        botPlaceholderTimer = null;
      }
    };

    const ensureBotMessageVisible = () => {
      if (botMessageVisible) {
        return;
      }
      botMessageVisible = true;
      currentMessages.value.push(botMessage);
    };

    const streamMessage = async () => {
      await ensureParentSession();
      await sendMessageApi(conversationId, content, selectedLanguage, assistantId || undefined, (chunk: string) => {
        try {
          const data = JSON.parse(chunk);
          if (data.answer) {
            clearBotPlaceholderTimer();
            ensureBotMessageVisible();
            botMessage.content += data.answer;
            currentMessages.value = [...currentMessages.value];
          }
          if (data.event === 'manual_prompt' && data.bot_message?.content) {
            clearBotPlaceholderTimer();
            if (botMessageVisible && !botMessage.content) {
              currentMessages.value = currentMessages.value.filter((message) => message.id !== botMessage.id);
              botMessageVisible = false;
            }
            currentMessages.value.push({
              id: data.bot_message.id ?? `${Date.now()}-manual`,
              conversation_id: conversationId,
              sender_type: 'bot',
              content: data.bot_message.content,
              created_at: new Date().toISOString(),
            });
            currentMessages.value = [...currentMessages.value];
          }
          if (data.event === 'done' && data.bot_message) {
            clearBotPlaceholderTimer();
            ensureBotMessageVisible();
            botMessage.id = data.bot_message.id ?? botMessage.id;
            botMessage.content = data.bot_message.content ?? botMessage.content;
            currentMessages.value = [...currentMessages.value];
          }
          if (data.event === 'ai_disabled') {
            clearBotPlaceholderTimer();
            currentMessages.value = currentMessages.value.filter((message) => message.id !== botMessage.id);
            botMessageVisible = false;
            currentMessages.value = [...currentMessages.value];
          }
          if (data.error) {
            clearBotPlaceholderTimer();
            ensureBotMessageVisible();
            botMessage.content = '[发送失败]';
            currentMessages.value = [...currentMessages.value];
          }
        } catch (e) {
          // Ignore parsing errors for non-json chunks
        }
      });
    };

    try {
      await streamMessage();
    } catch (error) {
      clearBotPlaceholderTimer();
      if (error instanceof Error && /status:\s*(401|403)/.test(error.message)) {
        await ensureParentSession(true);
        await streamMessage();
        return;
      }
      throw error;
    }
  }

  return {
    conversations,
    currentMessages,
    loading,
    loadingMessages,
    fetchConversations,
    fetchMessages,
    createNewConversation,
    postMessage,
  };
});
