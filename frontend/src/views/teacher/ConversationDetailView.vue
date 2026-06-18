<template>
  <div class="conversation-detail-view">
    <!-- 返回按钮 -->
    <div class="back-header">
      <button class="back-btn glass" @click="router.back()">
        <span class="back-icon">←</span>
        <span>{{ t('common.backToList') }}</span>
      </button>
    </div>

    <!-- 会话卡片 -->
    <div class="conversation-card glass">
      <div class="card-header">
        <h3 class="card-title">💬 {{ t('conversation.title') }}</h3>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <el-skeleton :rows="8" animated />
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="error-state">
        <el-alert :title="error" type="error" show-icon />
      </div>

      <!-- 消息列表 -->
      <div v-else class="messages-wrapper">
      <div
        v-for="message in messages"
        :key="message.id"
        class="message-item"
        :class="[`sender-${message.sender_type}`]"
      >
        <div class="meta">
          <span class="sender">{{ formatSender(message.sender_type, message.sender_name) }}</span>
          <span class="timestamp">{{ formatTime(message.created_at) }}</span>
        </div>
        <div class="content">
          <!-- 普通文本内容 -->
          <span v-if="!hasAppointmentInfo(message.content)">{{ message.content }}</span>
          
          <!-- 包含预约信息的内容 -->
          <div v-else class="appointment-message">
            <div class="text-content">{{ getTextContent(message.content) }}</div>
              <div class="appointment-card">
                <div class="appointment-icon">📅</div>
                <div class="appointment-details">
                  <div class="appointment-title">{{ t('conversation.appointmentInfo') }}</div>
                  <div class="appointment-info">
                    <div class="info-row">
                      <span class="info-label">{{ t('conversation.campus') }}：</span>
                      <span class="info-value">{{ getAppointmentInfo(message.content).campus }}</span>
                    </div>
                    <div class="info-row">
                      <span class="info-label">{{ t('conversation.time') }}：</span>
                      <span class="info-value">{{ getAppointmentInfo(message.content).timeslot }}</span>
                    </div>
                    <div class="info-row" v-if="getAppointmentInfo(message.content).parent_name">
                      <span class="info-label">{{ t('conversation.parentName') }}：</span>
                      <span class="info-value">{{ getAppointmentInfo(message.content).parent_name }}</span>
                    </div>
                    <div class="info-row" v-if="getAppointmentInfo(message.content).phone">
                      <span class="info-label">{{ t('conversation.phone') }}：</span>
                      <span class="info-value">{{ getAppointmentInfo(message.content).phone }}</span>
                    </div>
                    <div class="info-row" v-if="getAppointmentInfo(message.content).email">
                      <span class="info-label">{{ t('conversation.email') }}：</span>
                      <span class="info-value">{{ getAppointmentInfo(message.content).email }}</span>
                    </div>
                  </div>
                  <div class="appointment-status">✅ {{ t('conversation.appointmentConfirmed') }}</div>
                </div>
              </div>
          </div>
        </div>
      </div>
        <div v-if="messages.length === 0" class="empty-state">
          <div class="empty-icon">💬</div>
          <div class="empty-text">{{ t('conversation.noMessages') }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getTeacherConversationMessages } from '@/api/teacher';
import { useI18n } from 'vue-i18n';
import type { Message } from '@/types/message';
import { formatChinaDateTime } from '@/utils/time';

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const conversationId = route.params.id as string;

const messages = ref<Message[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const formatSender = (senderType: string, senderName?: string) => {
  if (senderType === 'parent') return senderName || t('conversation.parent');
  if (senderType === 'bot') return t('conversation.bot');
  if (senderType === 'teacher') return senderName || t('conversation.teacher');
  return senderName || senderType;
};

const formatTime = (value?: string) => {
  return formatChinaDateTime(value);
};

// 检查消息是否包含预约信息
const hasAppointmentInfo = (content: string): boolean => {
  return content.includes('[[APPOINTMENT]]');
};

// 获取预约信息
const getAppointmentInfo = (content: string) => {
  const match = content.match(/\[\[APPOINTMENT\]\]\{([^}]+)\}/);
  if (!match) return {};
  
  try {
    return JSON.parse(`{${match[1]}}`);
  } catch (e) {
    console.error('Failed to parse appointment info:', e);
    return {};
  }
};

// 获取文本内容（去除预约信息标记）
const getTextContent = (content: string): string => {
  return content.replace(/\[\[APPOINTMENT\]\]\{[^}]+\}/g, '').trim();
};

const fetchMessages = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await getTeacherConversationMessages(conversationId, { page: 1, page_size: 200 });
    messages.value = response.items;
  } catch (err) {
    console.error(err);
    error.value = t('conversation.loadError');
  }
  loading.value = false;
};

onMounted(() => {
  void fetchMessages();
});
</script>

<style scoped>
.conversation-detail-view {
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

/* 会话卡片 */
.conversation-card {
  padding: 30px;
  border-radius: 20px;
  min-height: 70vh;
}

.card-header {
  margin-bottom: 25px;
}

.card-title {
  font-size: 22px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
}

/* 加载和错误状态 */
.loading-state,
.error-state {
  padding: 40px 20px;
}

/* 消息列表 */
.messages-wrapper {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.message-item {
  padding: 20px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.4);
  transition: all 0.3s ease;
}

.message-item:hover {
  background: rgba(255, 255, 255, 0.6);
  transform: translateX(3px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
}

.message-item.sender-parent {
  background: rgba(52, 152, 219, 0.15);
}

.message-item.sender-bot {
  background: rgba(149, 165, 166, 0.1);
}

.message-item.sender-teacher {
  background: rgba(241, 196, 15, 0.15);
}

.meta {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: rgba(44, 62, 80, 0.6);
  margin-bottom: 10px;
  font-weight: 600;
}

.sender {
  color: #2c3e50;
  font-weight: 700;
}

.timestamp {
  color: rgba(44, 62, 80, 0.5);
}

.content {
  white-space: pre-wrap;
  line-height: 1.7;
  color: #2c3e50;
  font-size: 14px;
}

/* 预约信息卡片样式 */
.appointment-message {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.text-content {
  line-height: 1.6;
}

.appointment-card {
  display: flex;
  gap: 15px;
  padding: 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
  border: 2px solid #3498db;
  border-radius: 12px;
  margin-top: 8px;
  box-shadow: 0 2px 8px rgba(52, 152, 219, 0.1);
  transition: all 0.3s ease;
}

.appointment-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(52, 152, 219, 0.15);
}

.appointment-icon {
  font-size: 32px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #ebf5fb 0%, #d6eaf8 100%);
  border-radius: 10px;
}

.appointment-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.appointment-title {
  font-size: 15px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 2px;
}

.appointment-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-row {
  display: flex;
  align-items: center;
  font-size: 13px;
  line-height: 1.5;
}

.info-label {
  color: #7f8c8d;
  font-weight: 500;
  min-width: 55px;
}

.info-value {
  color: #2c3e50;
  font-weight: 600;
}

.appointment-status {
  margin-top: 4px;
  padding: 6px 12px;
  background: linear-gradient(135deg, #d5f4e6 0%, #e8f8f5 100%);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #27ae60;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  color: rgba(44, 62, 80, 0.6);
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .conversation-card {
    padding: 20px;
  }
  
  .card-title {
    font-size: 20px;
  }
  
  .message-item {
    padding: 15px;
  }
  
  .meta {
    font-size: 12px;
  }
  
  .content {
    font-size: 13px;
  }
}
</style>
