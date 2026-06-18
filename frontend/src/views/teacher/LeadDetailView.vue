<template>
  <div class="lead-detail-view">
    <!-- 返回按钮 -->
    <div class="back-header">
      <button class="back-btn glass" @click="$router.back()">
        <span class="back-icon">←</span>
        <span>{{ t('common.backToList') }}</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container glass">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-container glass">
      <el-alert :title="error" type="error" show-icon />
    </div>

    <!-- 内容区域 -->
    <div v-else-if="lead" class="detail-wrapper">
      <!-- 左侧：线索详情与跟进 -->
      <div class="detail-section glass">
        <!-- 线索基本信息卡片 -->
        <div class="info-card">
          <div class="card-header">
            <h3 class="card-title">📋 {{ t('leads.detail.title') }}</h3>
            <div class="status-badges">
              <span v-if="lead.is_high_intent" class="badge success">🔥 {{ t('leads.detail.statusHighIntent') }}</span>
              <span v-if="lead.needs_manual_callback" class="badge danger">⚠️ {{ t('leads.detail.statusManualCallback') }}</span>
            </div>
          </div>

          <div class="info-grid">
            <div class="info-item">
              <div class="info-label">👤 {{ t('leads.detail.parentName') }}</div>
              <div class="info-value">{{ lead.display_name || lead.parent_name || t('leads.notProvided') }}</div>
            </div>
            <div class="info-item">
              <div class="info-label">📱 {{ t('leads.detail.contactPhone') }}</div>
              <div class="info-value">{{ lead.display_phone || lead.parent_phone || t('leads.notProvided') }}</div>
            </div>
            <div class="info-item">
              <div class="info-label">📍 {{ t('leads.detail.intendedCampus') }}</div>
              <div class="info-value campus">{{ getCampusText(lead.campus) }}</div>
            </div>
            <div class="info-item">
              <div class="info-label">🏷️ {{ t('leads.detail.wecomStatus') }}</div>
              <div class="info-value">
                <span class="status-badge" :class="getWecomStatusClass(lead.wecom_status)">
                  {{ getWecomStatusText(lead.wecom_status) }}
                </span>
              </div>
            </div>
            <div class="info-item">
              <div class="info-label">📇 {{ t('leads.detail.wecomNickname') }}</div>
              <div class="info-value">
                {{ lead.wecom_contact_name || t('leads.notProvided') }}
              </div>
            </div>
            <div class="info-item">
              <div class="info-label">🆔 {{ t('leads.detail.wecomId') }}</div>
              <div class="info-value">
                {{ lead.wecom_contact_id || t('leads.detail.notSynced') }}
              </div>
            </div>
            <div class="info-item">
              <div class="info-label">👩‍🏫 {{ t('leads.detail.followUpOwner') }}</div>
              <div class="info-value owner-value">
                <span>{{ getOwnerName() }}</span>
                <span v-if="lead.follow_up_owner?.wechat_id" class="owner-wechat">
                  (WeCom: {{ lead.follow_up_owner.wechat_id }})
                </span>
              </div>
            </div>
            <div class="info-item">
              <div class="info-label">⏱ {{ t('leads.detail.consultationTime') }}</div>
              <div class="info-value">
                {{ getConsultationTime() }}
              </div>
            </div>
            <div class="info-item full-width">
              <div class="info-label">📝 {{ t('leads.aiSummary') }}</div>
              <div class="info-value summary">{{ getLeadSummary() }}</div>
            </div>
            <div class="info-item full-width" v-if="lead.appointment">
              <div class="info-label">📅 {{ t('leads.detail.appointmentInfo') }}</div>
              <div class="appointment-info">
                <div class="appointment-row">
                  <span>{{ t('leads.detail.timeSlot') }}: {{ lead.appointment.timeslot || t('leads.detail.pending') }}</span>
                </div>
                <div class="appointment-row">
                  <span>{{ t('leads.detail.campus') }}: {{ getAppointmentCampus() }}</span>
                </div>
                <div class="appointment-row">
                  <span>{{ t('leads.detail.parentName') }}: {{ getAppointmentParentName() }}</span>
                </div>
                <div class="appointment-row">
                  <span>{{ t('leads.detail.contactPhone') }}: {{ getAppointmentPhone() }}</span>
                </div>
                <div class="appointment-row">
                  <span>{{ t('chat.email') }}: {{ getAppointmentEmail() }}</span>
                </div>
                <span 
                  class="appointment-status" 
                  :class="getAppointmentStatusClass(lead.appointment.status)"
                >
                  {{ getAppointmentStatusLabel(lead.appointment.status) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 添加跟进记录 -->
        <div class="follow-up-card">
          <h3 class="card-title">✍️ {{ t('leads.detail.addNote') }}</h3>
          <textarea 
            v-model="newNote" 
            class="note-textarea"
            rows="4" 
            :placeholder="t('leads.detail.notePlaceholder')"
          />
          <button class="submit-btn" @click="handleAddNote">
            <span class="btn-icon">💾</span>
            <span>{{ t('leads.detail.saveNote') }}</span>
          </button>
        </div>

        <!-- 历史备注 -->
        <div class="notes-card">
          <h3 class="card-title">📌 {{ t('leads.detail.noteHistory') }}</h3>
          <div v-if="lead.notes && lead.notes.length" class="notes-list">
            <div v-for="(note, index) in lead.notes" :key="index" class="note-item">
              <div class="note-header">
                <span class="note-author">{{ note.created_by_name || t('leads.detail.system') }}</span>
                <span class="note-time">{{ formatChinaDateTime(note.created_at) }}</span>
                <div class="note-actions">
                  <button class="note-action edit" @click="handleEditNote(note.id as string, note.content, note.follow_up_method)">{{ t('common.edit') }}</button>
                  <button class="note-action delete" @click="handleDeleteNote(note.id as string)">{{ t('common.delete') }}</button>
                </div>
              </div>
              <div class="note-content">{{ note.content }}</div>
            </div>
          </div>
          <div v-else class="empty-notes">
            <div class="empty-icon">📭</div>
            <div class="empty-text">{{ t('leads.detail.noNotes') }}</div>
          </div>
        </div>
      </div>

      <!-- 右侧：对话记录 -->
      <div class="conversation-section glass">
        <div class="card-header">
          <h3 class="card-title">💬 {{ t('leads.detail.conversationRecord') }}</h3>
          <button
            v-if="lead.conversation_id"
            class="ai-toggle-btn"
            :class="{ off: !aiReplyEnabled }"
            :disabled="togglingAiReply"
            @click="handleToggleAiReply"
          >
            {{ togglingAiReply ? '切换中...' : aiReplyEnabled ? 'AI回复已开启' : 'AI回复已关闭' }}
          </button>
        </div>
        <div class="messages-container">
          <div 
            v-for="message in messages" 
            :key="message.id" 
            class="message-item" 
            :class="`sender-${message.sender_type}`"
          >
            <div class="message-avatar">{{ getMessageAvatar(message.sender_type) }}</div>
            <div class="message-bubble">
              <div class="sender-name">{{ getMessageSenderName(message.sender_type, message.sender_name) }}</div>
              <div v-if="getMessageTextContent(message.content)" class="message-content">
                {{ getMessageTextContent(message.content) }}
              </div>
              <div
                v-if="getAppointmentInfo(message.content)"
                class="message-info-card appointment-message-card"
              >
                <div class="message-info-icon">✓</div>
                <div class="message-info-body">
                  <div class="message-info-title">{{ t('chat.appointmentConfirmed') }}</div>
                  <div
                    v-for="field in appointmentFields(getAppointmentInfo(message.content))"
                    :key="field.label"
                    class="message-info-line"
                  >
                    <span class="message-info-label">{{ field.label }}</span>
                    <span>{{ field.value }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="!messages.length" class="empty-messages">
            <div class="empty-icon">💬</div>
            <div class="empty-text">{{ t('conversation.noMessages') }}</div>
          </div>
        </div>
        <div v-if="lead.conversation_id" class="manual-reply-card">
          <h4 class="reply-title">人工回复家长</h4>
          <textarea
            v-model="manualReply"
            class="reply-textarea"
            rows="4"
            placeholder="输入人工回复内容，发送后家长端可见"
            :disabled="replying"
          />
          <div class="reply-actions">
            <button class="submit-btn reply-btn" :disabled="replying || !manualReply.trim()" @click="handleSendManualReply">
              <span class="btn-icon">📨</span>
              <span>{{ replying ? '发送中...' : '发送给家长' }}</span>
            </button>
          </div>
        </div>

        <div class="card-header wecom-header">
          <h3 class="card-title">🏢 {{ t('leads.detail.wecomConversationRecord') }}</h3>
        </div>
        <div class="messages-container wecom-log">
          <div 
            v-if="lead.wecom_chat_history && lead.wecom_chat_history.length"
            class="wecom-list"
          >
            <div 
              v-for="msg in lead.wecom_chat_history" 
              :key="msg.id"
              class="message-item"
              :class="`sender-${msg.direction}`"
            >
              <div class="message-avatar">
                {{ msg.direction === 'parent' ? '👤' : msg.direction === 'teacher' ? '👩‍🏫' : '🤖' }}
              </div>
              <div class="message-bubble">
                <div class="sender-name">
                  {{ getWecomSenderName(msg.direction) }}
                  <span class="message-time">{{ formatChinaDateTime(msg.sent_at) }}</span>
                </div>
                <div class="message-content">{{ msg.content }}</div>
              </div>
            </div>
          </div>
          <div v-else class="empty-messages">
            <div class="empty-icon">💬</div>
            <div class="empty-text">{{ t('leads.detail.noWecomMessages') }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useLeadDetailStore } from '@/stores/leadDetail';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useI18n } from 'vue-i18n';
import { formatChinaDateTime } from '@/utils/time';

const route = useRoute();
const { t, locale } = useI18n();
const leadDetailStore = useLeadDetailStore();
const { lead, messages, loading, error, aiReplyEnabled } = storeToRefs(leadDetailStore);

const leadId = route.params.id as string;
const newNote = ref('');
const deleting = ref(false);
const manualReply = ref('');
const replying = ref(false);
const togglingAiReply = ref(false);
const APPOINTMENT_PATTERN = /\[\[APPOINTMENT\]\](\{[^]*?\})(?!\s*\{)/;
const APPOINTMENT_MARKER = /\[\[APPOINTMENT\]\]\{[^]*?\}(?!\s*\{)/g;

type AppointmentPayload = {
  campus?: string;
  timeslot?: string;
  parent_name?: string;
  phone?: string;
  email?: string;
};

onMounted(async () => {
  await leadDetailStore.fetchLead(leadId, locale.value);
});

watch(
  () => locale.value,
  (value) => {
    void leadDetailStore.fetchLead(leadId, value);
  }
);

const getAppointmentStatusLabel = (status?: string) => {
  if (status === 'pending') return `⏳ ${t('leads.detail.appointmentPending')}`;
  if (status === 'confirmed') return `✅ ${t('leads.detail.appointmentConfirmed')}`;
  if (status === 'rejected') return `🔄 ${t('leads.detail.appointmentRejected')}`;
  return `❌ ${t('leads.detail.appointmentNone')}`;
};

const getAppointmentStatusClass = (status?: string) => {
  if (status === 'pending') return 'status-pending';
  if (status === 'confirmed') return 'status-confirmed';
  if (status === 'rejected') return 'status-rejected';
  return 'status-none';
};

const getWecomStatusText = (status?: string) => {
  if (status === 'added') return t('leads.statusAdded');
  if (status === 'pending') return t('leads.statusPendingBind');
  return t('leads.statusNotAdded');
};

const getWecomStatusClass = (status?: string) => {
  if (status === 'added') return 'status-confirmed';
  if (status === 'pending') return 'status-pending';
  return 'status-none';
};

const getLeadSummary = () => {
  const summary = locale.value === 'en'
    ? (lead.value?.en_summary || lead.value?.summary)
    : lead.value?.summary;
  if (!summary || !summary.trim()) {
    return t('leads.noSummary');
  }
  if (summary === '暂无有效信息' || summary === 'No valid summary yet') {
    return t('leads.noSummary');
  }
  return summary;
};

const parseMarkerPayload = <T,>(content: string, pattern: RegExp): T | null => {
  const match = content.match(pattern);
  if (!match?.[1]) {
    return null;
  }
  try {
    return JSON.parse(match[1]) as T;
  } catch (error) {
    console.error('Failed to parse marker payload:', error);
    return null;
  }
};

const getAppointmentInfo = (content?: string | null): AppointmentPayload | null => {
  if (!content) {
    return null;
  }
  return parseMarkerPayload<AppointmentPayload>(content, APPOINTMENT_PATTERN);
};

const getMessageTextContent = (content?: string | null) => {
  if (!content) {
    return '';
  }
  return content
    .replace(APPOINTMENT_MARKER, '')
    .replace(/\n[ \t]*\n+/g, '\n')
    .trim();
};

const appointmentFields = (info: AppointmentPayload | null) => {
  if (!info) {
    return [];
  }
  return [
    { label: `${t('chat.campus')}：`, value: info.campus },
    { label: `${t('chat.time')}：`, value: info.timeslot },
    { label: `${t('chat.parent')}：`, value: info.parent_name },
    { label: `${t('chat.phone')}：`, value: info.phone },
    { label: `${t('chat.email')}：`, value: info.email },
  ].filter((field) => Boolean(field.value));
};

const getCampusText = (campus: string | null | undefined) => {
  switch (campus) {
    case '浦东':
    case 'Pudong':
      return t('leads.campusPudong');
    case '浦西':
    case 'Puxi':
      return t('leads.campusPuxi');
    case '临港':
    case 'Lingang':
      return t('leads.campusLingang');
    case undefined:
    case null:
    case '':
      return t('leads.campusUnknown');
    default:
      return campus;
  }
};

const getOwnerName = () => {
  const name = lead.value?.follow_up_owner?.name;
  if (!name) {
    return t('leads.followUpOwnerNone');
  }
  if (name === '默认学校管理员' || name === 'Default School Admin') {
    return t('teacher.layout.defaultSchoolAdmin');
  }
  if (name === '默认超级管理员' || name === 'Default Super Admin') {
    return t('teacher.layout.defaultSuperAdmin');
  }
  return name;
};

const getConsultationTime = () => {
  const storedFirstMessageAt = formatChinaDateTime(lead.value?.first_message_at);
  if (storedFirstMessageAt) {
    return storedFirstMessageAt;
  }

  const firstParentMessageAt = messages.value.find((message) => message.sender_type === 'parent')?.created_at;
  return formatChinaDateTime(firstParentMessageAt) || '—';
};

const getAppointmentParentName = () => {
  const appointmentName = lead.value?.appointment?.parent_name || lead.value?.appointment?.guardian_name;
  return appointmentName || lead.value?.display_name || lead.value?.parent_name || t('leads.notProvided');
};

const getAppointmentPhone = () => {
  return lead.value?.appointment?.phone || lead.value?.display_phone || lead.value?.parent_phone || t('leads.notProvided');
};

const getAppointmentEmail = () => {
  return lead.value?.appointment?.email || lead.value?.parent_email || t('leads.notProvided');
};

const getAppointmentCampus = () => {
  const campus = lead.value?.appointment?.campus || lead.value?.campus;
  return campus ? getCampusText(campus) : t('leads.detail.pending');
};

const getMessageSenderName = (senderType?: string, senderName?: string) => {
  if (senderType === 'parent') return t('conversation.parent');
  if (senderType === 'teacher') return t('conversation.teacher');
  if (senderType === 'bot') return t('conversation.bot');
  return senderName || senderType || t('leads.detail.system');
};

const getWecomSenderName = (direction?: string) => {
  if (direction === 'parent') return t('conversation.parent');
  if (direction === 'teacher') return t('conversation.teacher');
  return t('leads.detail.system');
};

const getMessageAvatar = (senderType: string) => {
  if (senderType === 'parent') return '👤';
  if (senderType === 'bot') return '🤖';
  if (senderType === 'teacher') return '👨‍🏫';
  return '💬';
};

const handleAddNote = async () => {
  if (!newNote.value.trim()) {
    ElMessage.warning(t('leads.detail.noteRequired'));
    return;
  }
  try {
    await leadDetailStore.addNote(leadId, { content: newNote.value, follow_up_method: 'other' });
    ElMessage.success(t('leads.detail.noteSaved'));
    newNote.value = '';
  } catch (e) {
    console.error(e);
    ElMessage.error(t('leads.detail.noteSaveError'));
  }
};

const handleEditNote = async (noteId: string | null | undefined, currentContent?: string, followUpMethod?: string | null) => {
  if (!noteId) return;
  try {
    const { value } = await ElMessageBox.prompt(t('leads.detail.editNoteContent'), t('leads.detail.editNoteTitle'), {
      inputValue: currentContent || '',
      inputPlaceholder: t('leads.detail.editNotePlaceholder'),
      confirmButtonText: t('common.save'),
      cancelButtonText: t('common.cancel'),
    });
    if (value && value.trim()) {
      await leadDetailStore.updateNote(leadId, noteId, { content: value.trim(), follow_up_method: followUpMethod || 'other' });
      ElMessage.success(t('leads.detail.noteUpdated'));
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e);
      ElMessage.error(t('leads.detail.noteUpdateError'));
    }
  }
};

const handleDeleteNote = async (noteId: string | null | undefined) => {
  if (!noteId || deleting.value) return;
  try {
    await ElMessageBox.confirm(t('leads.detail.deleteNoteConfirm'), t('leads.detail.deleteNoteTitle'), { type: 'warning' });
    deleting.value = true;
    await leadDetailStore.removeNote(leadId, noteId);
    ElMessage.success(t('leads.detail.noteDeleted'));
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e);
      ElMessage.error(t('leads.detail.noteDeleteError'));
    }
  } finally {
    deleting.value = false;
  }
};

const handleSendManualReply = async () => {
  const conversationId = lead.value?.conversation_id;
  const content = manualReply.value.trim();
  if (!conversationId) {
    ElMessage.warning('当前线索没有关联会话');
    return;
  }
  if (!content || replying.value) {
    return;
  }
  try {
    replying.value = true;
    await leadDetailStore.sendManualReply(conversationId, content);
    manualReply.value = '';
    ElMessage.success('人工回复已发送，家长端可见');
  } catch (e: any) {
    console.error(e);
    ElMessage.error(e?.response?.data?.detail || '发送人工回复失败');
  } finally {
    replying.value = false;
  }
};

const handleToggleAiReply = async () => {
  const conversationId = lead.value?.conversation_id;
  if (!conversationId || togglingAiReply.value) {
    return;
  }
  try {
    togglingAiReply.value = true;
    const nextEnabled = !aiReplyEnabled.value;
    await leadDetailStore.setAiReplyEnabled(conversationId, nextEnabled);
    ElMessage.success(nextEnabled ? '已开启 AI 回复' : '已关闭 AI 回复');
  } catch (e: any) {
    console.error(e);
    ElMessage.error(e?.response?.data?.detail || '切换 AI 回复失败');
  } finally {
    togglingAiReply.value = false;
  }
};
</script>

<style scoped>
.lead-detail-view {
  padding: 0;
}

/* 毛玻璃效果 */
.glass {
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
}

/* 返回按钮 */
.back-header {
  margin-bottom: 20px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  color: #2c3e50;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.4);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}

.back-icon {
  font-size: 20px;
}

/* 加载和错误状态 */
.loading-container,
.error-container {
  padding: 40px;
  border-radius: 20px;
}

/* 主容器 */
.detail-wrapper {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  min-height: calc(100vh - 200px);
}

/* 左侧：详情区域 */
.detail-section {
  padding: 30px;
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-title {
  font-size: 20px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
}

/* 状态徽章 */
.status-badges {
  display: flex;
  gap: 10px;
}

.badge {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.badge.success {
  background: rgba(46, 204, 113, 0.2);
  color: #27ae60;
}

.badge.danger {
  background: rgba(231, 76, 60, 0.2);
  color: #c0392b;
}

/* 信息网格 */
.info-card {
  background: rgba(255, 255, 255, 0.3);
  padding: 25px;
  border-radius: 15px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item.full-width {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 13px;
  color: rgba(44, 62, 80, 0.7);
  font-weight: 600;
}

.info-value {
  font-size: 15px;
  color: #2c3e50;
  font-weight: 500;
}

.info-value.campus {
  padding: 6px 12px;
  background: rgba(52, 152, 219, 0.15);
  color: #2980b9;
  border-radius: 8px;
  display: inline-block;
  width: fit-content;
}

.info-value.score {
  font-size: 20px;
  font-weight: 700;
  color: #3498db;
}

.info-value.summary {
  line-height: 1.6;
  color: rgba(44, 62, 80, 0.9);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.status-confirmed {
  background: rgba(46, 204, 113, 0.15);
  color: #27ae60;
}

.status-pending {
  background: rgba(241, 196, 15, 0.2);
  color: #c29d0b;
}

.status-rejected {
  background: rgba(52, 152, 219, 0.15);
  color: #2980b9;
}

.status-none {
  background: rgba(149, 165, 166, 0.15);
  color: #7f8c8d;
}

.owner-value {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.owner-wechat {
  font-size: 13px;
  color: #606266;
}

/* 预约信息 */
.appointment-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 15px;
  background: rgba(52, 152, 219, 0.08);
  border-radius: 10px;
}

.appointment-row {
  font-size: 14px;
  color: #2c3e50;
}

.appointment-status {
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  display: inline-block;
  margin-top: 8px;
  width: fit-content;
}

.appointment-status.status-pending {
  background: rgba(241, 196, 15, 0.2);
  color: #f39c12;
}

.appointment-status.status-confirmed {
  background: rgba(46, 204, 113, 0.2);
  color: #27ae60;
}

.appointment-status.status-rejected {
  background: rgba(52, 152, 219, 0.2);
  color: #2980b9;
}

.appointment-status.status-none {
  background: rgba(231, 76, 60, 0.2);
  color: #c0392b;
}

/* 跟进记录卡片 */
.follow-up-card {
  background: rgba(255, 255, 255, 0.3);
  padding: 25px;
  border-radius: 15px;
}

.note-textarea {
  width: 100%;
  padding: 15px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.4);
  font-size: 14px;
  color: #2c3e50;
  font-family: inherit;
  line-height: 1.6;
  resize: vertical;
  transition: all 0.3s ease;
  margin-top: 15px;
  margin-bottom: 15px;
}

.note-textarea:focus {
  outline: none;
  border-color: rgba(52, 152, 219, 0.6);
  background: rgba(255, 255, 255, 0.6);
  box-shadow: 0 4px 15px rgba(52, 152, 219, 0.2);
}

.submit-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 28px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #27ae60, #229954);
  color: white;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(39, 174, 96, 0.4);
}

.btn-icon {
  font-size: 16px;
}

/* 历史备注 */
.notes-card {
  background: rgba(255, 255, 255, 0.3);
  padding: 25px;
  border-radius: 15px;
}

.notes-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-top: 15px;
}

.note-item {
  padding: 18px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 12px;
  border-left: 4px solid #3498db;
  transition: all 0.3s ease;
}

.note-item:hover {
  background: rgba(255, 255, 255, 0.7);
  transform: translateX(5px);
}

.note-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.note-author {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}

.note-time {
  font-size: 12px;
  color: rgba(44, 62, 80, 0.6);
}

.note-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.note-action {
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(52, 152, 219, 0.08);
  color: #2c3e50;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.note-action.edit {
  background: rgba(52, 152, 219, 0.12);
  border-color: rgba(52, 152, 219, 0.2);
}

.note-action.delete {
  background: rgba(231, 76, 60, 0.08);
  border-color: rgba(231, 76, 60, 0.18);
  color: #c0392b;
}

.note-action:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
}

.note-content {
  font-size: 14px;
  color: rgba(44, 62, 80, 0.9);
  line-height: 1.6;
}

.empty-notes {
  text-align: center;
  padding: 40px 20px;
  margin-top: 15px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  font-size: 14px;
  color: rgba(44, 62, 80, 0.6);
}

/* 右侧：对话区域 */
.conversation-section {
  padding: 30px;
  border-radius: 20px;
  display: flex;
  flex-direction: column;
}

.conversation-section .card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ai-toggle-btn {
  border: 1px solid rgba(56, 142, 60, 0.28);
  background: rgba(56, 142, 60, 0.12);
  color: #237a34;
  border-radius: 999px;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ai-toggle-btn.off {
  border-color: rgba(198, 40, 40, 0.24);
  background: rgba(198, 40, 40, 0.12);
  color: #b42318;
}

.ai-toggle-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.messages-container {
  flex: 0 0 auto;
  max-height: 420px;
  overflow-y: auto;
  padding: 15px;
  margin-top: 15px;
}

.manual-reply-card {
  margin-top: 18px;
  padding: 18px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.5);
}

.reply-title {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 700;
  color: #2c3e50;
}

.reply-textarea {
  width: 100%;
  min-height: 110px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(180, 196, 220, 0.9);
  background: rgba(255, 255, 255, 0.92);
  color: #2c3e50;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
}

.reply-textarea:focus {
  outline: none;
  border-color: rgba(76, 125, 255, 0.9);
  box-shadow: 0 0 0 3px rgba(76, 125, 255, 0.12);
}

.reply-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.reply-btn {
  min-width: 160px;
}

.messages-container::-webkit-scrollbar {
  width: 8px;
}

.messages-container::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: flex-start;
}

.message-item.sender-parent {
  flex-direction: row-reverse;
}

.message-avatar {
  font-size: 28px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(52, 152, 219, 0.1);
}

.message-bubble {
  max-width: min(100%, 420px);
  padding: 12px 14px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.5);
}

.message-item.sender-parent .message-bubble {
  background: rgba(52, 152, 219, 0.2);
}

.sender-name {
  font-size: 12px;
  color: rgba(44, 62, 80, 0.6);
  margin-bottom: 6px;
  font-weight: 600;
}

.message-content {
  font-size: 14px;
  color: #2c3e50;
  line-height: 1.6;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.message-info-card {
  margin-top: 10px;
  display: flex;
  gap: 10px;
  padding: 14px;
  border-radius: 18px;
}

.appointment-message-card {
  background: linear-gradient(135deg, rgba(227, 239, 255, 0.92), rgba(239, 246, 255, 0.96));
}

.message-info-icon {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  background: #356cf4;
  font-weight: 700;
}

.message-info-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.message-info-title {
  color: #1f2f49;
  font-size: 14px;
  font-weight: 700;
}

.message-info-line {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  color: #30425e;
  font-size: 13px;
  line-height: 1.55;
}

.message-info-label {
  color: rgba(48, 66, 94, 0.68);
}

.message-time {
  margin-left: 8px;
  font-size: 12px;
  color: rgba(44, 62, 80, 0.6);
  font-weight: 400;
}

.wecom-log {
  margin-top: 30px;
  max-height: 320px;
  border-top: 1px solid rgba(255, 255, 255, 0.4);
}

.wecom-log .message-item {
  padding: 12px 0;
  border-bottom: 1px dashed rgba(0, 0, 0, 0.05);
  margin-bottom: 0;
}

.empty-messages {
  text-align: center;
  padding: 60px 20px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .detail-wrapper {
    grid-template-columns: 1fr;
  }
  
  .info-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .detail-section,
  .conversation-section {
    padding: 20px;
  }
  
  .info-card,
  .follow-up-card,
  .notes-card {
    padding: 20px;
  }
  
  .card-title {
    font-size: 18px;
  }
  
  .message-bubble {
    max-width: 85%;
  }
}
</style>
