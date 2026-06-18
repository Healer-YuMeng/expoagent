import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getLead, addFollowUpNote, updateFollowUpNote, deleteFollowUpNote } from '@/api/lead';
import { getTeacherConversationMessages, sendTeacherConversationMessage, updateTeacherConversationAiReply } from '@/api/teacher';
import type { Lead, AddFollowUpNoteRequest } from '@/types';
import type { Message } from '@/types/message'; // Assuming this exists

export const useLeadDetailStore = defineStore('leadDetail', () => {
  const lead = ref<Lead | null>(null);
  const messages = ref<Message[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const currentLanguage = ref<string | undefined>(undefined);
  const aiReplyEnabled = ref(true);

  async function fetchLead(id: string, language?: string) {
    currentLanguage.value = language;
    loading.value = true;
    error.value = null;
    try {
      const leadData = await getLead(id, language);
      lead.value = leadData;
      if (leadData.conversation_id) {
        await fetchMessages(leadData.conversation_id);
      }
    } catch (e) {
      error.value = '无法加载线索详情';
      console.error(e);
    }
    loading.value = false;
  }

  async function fetchMessages(conversationId: string) {
    try {
      // Assuming getConversationMessages is adapted for admin/teacher use
      const response = await getTeacherConversationMessages(conversationId, { page: 1, page_size: 200 });
      messages.value = response.items;
      aiReplyEnabled.value = response.ai_reply_enabled !== false;
    } catch (e) {
      error.value = '无法加载对话记录';
      console.error(e);
    }
  }

  async function addNote(id: string, note: AddFollowUpNoteRequest) {
    if (!lead.value) return;
    try {
      await addFollowUpNote(id, { ...note, follow_up_method: note.follow_up_method || 'other' });
      // For simplicity, we just refetch the whole lead to get updated notes
      await fetchLead(id, currentLanguage.value);
    } catch (e) {
      console.error('Failed to add note', e);
      throw e;
    }
  }

  async function updateNote(leadId: string, noteId: string, payload: { content: string; follow_up_method?: string }) {
    try {
      await updateFollowUpNote(leadId, noteId, payload);
      await fetchLead(leadId, currentLanguage.value);
    } catch (e) {
      console.error('Failed to update note', e);
      throw e;
    }
  }

  async function removeNote(leadId: string, noteId: string) {
    try {
      await deleteFollowUpNote(leadId, noteId);
      await fetchLead(leadId, currentLanguage.value);
    } catch (e) {
      console.error('Failed to delete note', e);
      throw e;
    }
  }

  async function sendManualReply(conversationId: string, content: string) {
    const message = await sendTeacherConversationMessage(conversationId, { content });
    messages.value.push(message);
    return message;
  }

  async function setAiReplyEnabled(conversationId: string, enabled: boolean) {
    const response = await updateTeacherConversationAiReply(conversationId, enabled);
    aiReplyEnabled.value = response.ai_reply_enabled !== false;
    return response;
  }

  return {
    lead,
    messages,
    loading,
    error,
    aiReplyEnabled,
    fetchLead,
    addNote,
    updateNote,
    removeNote,
    sendManualReply,
    setAiReplyEnabled,
  };
});
