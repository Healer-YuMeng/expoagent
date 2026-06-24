<template>
  <div class="chat-page">
    <PaintBackground />

    <div class="chat-shell">
      <header class="chat-topbar">
        <div class="topbar-brand">
          <span class="brand-status-dot" aria-hidden="true"></span>
          <div class="brand-copy">
            <strong>在线聊天</strong>
            <span class="brand-status-text">系统在线</span>
          </div>
        </div>
        <div class="topbar-actions">
          <button class="topbar-link" type="button" @click="handleGoHome">
            {{ t('common.home') }}
          </button>
          <button class="topbar-link" type="button" @click="handleGoLogin">
            {{ t('common.login') }}
          </button>
        </div>
      </header>

      <main class="chat-panel">
        <section ref="messagesContainerRef" class="message-stream">
          <article
            v-for="message in displayedMessages"
            :key="message.id"
            class="message-row"
            :class="message.sender_type === 'parent' ? 'is-user' : 'is-bot'"
          >
            <div class="message-avatar">
              <span
                v-if="message.sender_type === 'parent'"
                class="user-avatar-icon"
                aria-hidden="true"
              >
                👤
              </span>
              <img
                v-else
                src="/xt.png"
                alt="Teacher avatar"
                class="teacher-avatar-image"
              />
            </div>

            <div class="message-bubble">
              <div
                v-if="message.sender_type === 'bot' && message.content === ''"
                class="typing-indicator"
              >
                <span></span>
                <span></span>
                <span></span>
              </div>

              <template v-else>
                <p v-if="getTextContent(message.content)" class="message-text">
                  {{ getTextContent(message.content) }}
                </p>

                <div v-if="getAppointmentInfo(message.content)" class="info-card appointment-card">
                  <div class="info-card-icon">✓</div>
                  <div class="info-card-body">
                    <div class="info-card-title">{{ t('chat.appointmentConfirmed') }}</div>
                    <div
                      v-for="field in appointmentFields(getAppointmentInfo(message.content))"
                      :key="field.label"
                      class="info-card-line"
                    >
                      <span class="info-label">{{ field.label }}</span>
                      <span>{{ field.value }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="getWechatQrInfo(message.content)" class="info-card qr-card">
                  <div class="info-card-body">
                    <div class="info-card-title">
                      {{ getWechatQrInfo(message.content)?.teacher_name || t('chat.title') }}
                    </div>
                    <div class="info-card-line">
                      <span class="info-label">{{ t('chat.campus') }}</span>
                      <span>{{ getWechatQrInfo(message.content)?.campus }}</span>
                    </div>
                    <div
                      v-if="getWechatQrInfo(message.content)?.wechat_id"
                      class="info-card-line"
                    >
                      <span class="info-label">WeChat</span>
                      <span>{{ getWechatQrInfo(message.content)?.wechat_id }}</span>
                    </div>
                    <img
                      v-if="getWechatQrInfo(message.content)?.qr_url"
                      :src="getWechatQrInfo(message.content)?.qr_url"
                      alt="WeChat QR"
                      class="qr-image"
                    />
                  </div>
                </div>
              </template>
            </div>
          </article>
        </section>
      </main>

      <footer class="composer composer-floating">
        <div v-if="assistantOptions.length" class="assistant-bar">
          <div class="assistant-copy">
            <span class="assistant-label">当前助手</span>
            <span class="assistant-tip">仅使用该助手绑定的知识库和提示词回答</span>
          </div>
          <div class="assistant-pills">
            <button
              v-for="assistant in assistantOptions"
              :key="assistant.id"
              type="button"
              class="assistant-pill"
              :class="{ active: selectedAssistantId === assistant.id }"
              :disabled="isSending || isSwitchingAssistant"
              @click="handleAssistantSelect(assistant.id)"
            >
              {{ assistant.name }}
            </button>
          </div>
        </div>

        <div class="composer-inner">
          <input
            v-model="newMessage"
            type="text"
            class="composer-input"
            :placeholder="t('chat.inputPlaceholder')"
            :disabled="isSending"
            @keyup.enter="handleSendMessage"
          />
          <button
            type="button"
            class="composer-send"
            :aria-label="isSending ? t('common.sending') : t('common.send')"
            :disabled="isSending"
            @click="handleSendMessage"
          >
            <span class="composer-send-icon" aria-hidden="true">↑</span>
          </button>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useConversationStore } from '@/stores/conversation';
import { useI18n } from 'vue-i18n';
import {
  getParentWelcomeMessage,
  listParentAssistants,
  updateConversationAssistant,
  type ParentAssistantItem,
} from '@/api/conversation';
import PaintBackground from '@/components/PaintBackground.vue';
import { getAppStorageItem, setAppStorageItem } from '@/utils/browserStorage';

type AppointmentPayload = {
  campus?: string;
  timeslot?: string;
  parent_name?: string;
  phone?: string;
  email?: string;
};

type WechatQrPayload = {
  campus?: string;
  teacher_name?: string;
  qr_url?: string;
  wechat_id?: string;
};

const route = useRoute();
const router = useRouter();
const { t, locale } = useI18n();
const conversationStore = useConversationStore();
const { currentMessages } = storeToRefs(conversationStore);

const conversationId = route.params.id as string;
const newMessage = ref('');
const isSending = ref(false);
const isSwitchingAssistant = ref(false);
const messagesContainerRef = ref<HTMLDivElement | null>(null);
const localizedWelcomeMessage = ref('');
const assistantOptions = ref<ParentAssistantItem[]>([]);
const selectedAssistantId = ref('');
let refreshTimer: number | null = null;

const APPOINTMENT_PATTERN = /\[\[APPOINTMENT\]\](\{[^]*?\})(?!\s*\{)/;
const WECHAT_QR_PATTERN = /\[\[WECHAT_QR\]\](\{[^]*?\})(?!\s*\{)/;
const APPOINTMENT_MARKER = /\[\[APPOINTMENT\]\]\{[^]*?\}(?!\s*\{)/g;
const WECHAT_QR_MARKER = /\[\[WECHAT_QR\]\]\{[^]*?\}(?!\s*\{)/g;

const displayedMessages = computed(() => {
  if (!localizedWelcomeMessage.value) {
    return currentMessages.value;
  }
  const firstBotIndex = currentMessages.value.findIndex((message) => message.sender_type === 'bot');
  if (firstBotIndex === -1) {
    return currentMessages.value;
  }
  return currentMessages.value.map((message, index) => {
    if (index !== firstBotIndex) {
      return message;
    }
    return {
      ...message,
      content: localizedWelcomeMessage.value,
    };
  });
});

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight;
    }
  });
}

async function sendChatMessage(content: string) {
  if (!content.trim() || isSending.value) {
    return;
  }

  isSending.value = true;
  try {
    await conversationStore.postMessage(conversationId, content);
  } catch (error) {
    console.error('Failed to send message:', error);
  } finally {
    isSending.value = false;
  }
}

async function handleSendMessage() {
  if (!newMessage.value.trim() || isSending.value) {
    return;
  }

  const content = newMessage.value;
  newMessage.value = '';
  await sendChatMessage(content);
}

async function loadAssistants() {
  try {
    const response = await listParentAssistants({
      conversation_id: conversationId,
    });
    assistantOptions.value = response.items || [];

    const routeAssistantId = typeof route.query.assistant_id === 'string' ? route.query.assistant_id : '';
    const storedAssistantId = getAppStorageItem('selectedAssistantId') || '';
    const preferredAssistantId = response.selected_assistant_id || routeAssistantId || storedAssistantId;

    if (preferredAssistantId && assistantOptions.value.some((item) => item.id === preferredAssistantId)) {
      selectedAssistantId.value = preferredAssistantId;
      setAppStorageItem('selectedAssistantId', preferredAssistantId);
      return;
    }

    selectedAssistantId.value = '';
  } catch (error) {
    console.error('Failed to load assistants:', error);
    assistantOptions.value = [];
    selectedAssistantId.value = '';
  }
}

async function handleAssistantChange() {
  if (!selectedAssistantId.value || isSwitchingAssistant.value) {
    return;
  }

  isSwitchingAssistant.value = true;
  try {
    await updateConversationAssistant(conversationId, selectedAssistantId.value);
    setAppStorageItem('selectedAssistantId', selectedAssistantId.value);

    await router.replace({
      query: {
        ...route.query,
        assistant_id: selectedAssistantId.value,
      },
    });
  } catch (error) {
    console.error('Failed to switch assistant:', error);
    await loadAssistants();
  } finally {
    isSwitchingAssistant.value = false;
  }
}

async function handleAssistantSelect(assistantId: string) {
  if (!assistantId) {
    return;
  }
  selectedAssistantId.value = assistantId;
  await handleAssistantChange();
}

function handleGoHome() {
  router.push({ name: 'Index', query: route.query });
}

function handleGoLogin() {
  router.push({ name: 'Login' });
}

function parseMarkerPayload<T>(content: string, pattern: RegExp): T | null {
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
}

function getAppointmentInfo(content: string): AppointmentPayload | null {
  return parseMarkerPayload<AppointmentPayload>(content, APPOINTMENT_PATTERN);
}

function getWechatQrInfo(content: string): WechatQrPayload | null {
  return parseMarkerPayload<WechatQrPayload>(content, WECHAT_QR_PATTERN);
}

function getTextContent(content: string): string {
  return content
    .replace(APPOINTMENT_MARKER, '')
    .replace(WECHAT_QR_MARKER, '')
    .replace(/\n[ \t]*\n+/g, '\n')
    .trim();
}

function appointmentFields(info: AppointmentPayload | null) {
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
}

async function refreshLocalizedWelcomeMessage() {
  try {
    const response = await getParentWelcomeMessage(conversationId, locale.value);
    localizedWelcomeMessage.value = response.content || '';
  } catch (error) {
    console.error('Failed to load localized welcome message:', error);
    localizedWelcomeMessage.value = '';
  }
}

onMounted(() => {
  conversationStore.fetchMessages(conversationId);
  refreshLocalizedWelcomeMessage();
  loadAssistants();
  refreshTimer = window.setInterval(() => {
    if (!isSending.value) {
      void conversationStore.fetchMessages(conversationId);
    }
  }, 3000);
});

onUnmounted(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
});

watch(
  displayedMessages,
  () => {
    scrollToBottom();
  },
  { deep: true },
);

watch(
  () => locale.value,
  () => {
    refreshLocalizedWelcomeMessage();
  },
);
</script>

<style scoped>
.chat-page {
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: #ffffff;
}

.chat-shell {
  --chat-shell-width: min(100%, 1100px);
  position: relative;
  z-index: 10;
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px 18px;
  box-sizing: border-box;
}

.chat-topbar {
  width: var(--chat-shell-width);
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding: 14px 22px;
  border-radius: 999px;
  background: rgba(249, 251, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 12px 28px rgba(53, 62, 93, 0.1);
}

.topbar-link {
  border: 0;
  background: transparent;
  color: rgba(48, 63, 90, 0.88);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 20px;
}

.topbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #334560;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.topbar-brand strong {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.1;
}

.brand-status-text {
  color: rgba(66, 86, 118, 0.72);
  font-size: 12px;
  line-height: 1.2;
}

.brand-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #35c759;
  box-shadow:
    0 0 0 0 rgba(53, 199, 89, 0.45),
    0 0 18px rgba(53, 199, 89, 0.45);
  animation: onlinePulse 1.6s ease-out infinite;
}

.chat-panel {
  width: var(--chat-shell-width);
  flex: 0 0 auto;
  min-height: 0;
  height: min(740px, calc(100vh - 198px));
  display: flex;
  flex-direction: column;
  border-radius: 30px;
  background: rgba(252, 253, 255, 0.9);
  border: 1px solid rgba(220, 228, 239, 0.82);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow:
    0 24px 60px rgba(52, 57, 77, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.88);
  overflow: hidden;
}

.message-stream {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 26px 26px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background:
    radial-gradient(circle at 50% 22%, rgba(226, 235, 248, 0.34), transparent 44%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(247, 250, 255, 0.72));
}

.message-stream::-webkit-scrollbar {
  width: 8px;
}

.message-stream::-webkit-scrollbar-thumb {
  background: rgba(38, 53, 78, 0.18);
  border-radius: 999px;
}

.message-row {
  display: flex;
  gap: 10px;
  width: 100%;
  max-width: none;
  align-items: flex-end;
}

.message-row.is-user {
  flex-direction: row-reverse;
  justify-content: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  flex: 0 0 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 6px 18px rgba(62, 72, 98, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.96);
}

.teacher-avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 999px;
  object-fit: cover;
}

.message-row.is-user .message-avatar {
  background: linear-gradient(180deg, #ff8bb8, #f06b9c);
  color: #ffffff;
}

.user-avatar-icon {
  font-size: 17px;
  line-height: 1;
}

.message-bubble {
  flex: 0 0 auto;
  width: fit-content;
  min-width: 0;
  max-width: min(70%, 720px);
  padding: 12px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 10px 28px rgba(53, 64, 92, 0.06);
  border: 1px solid rgba(236, 239, 245, 0.96);
}

.message-row.is-bot .message-bubble {
  text-align: left;
}

.message-row.is-user .message-bubble {
  background: linear-gradient(180deg, rgba(242, 246, 255, 0.98), rgba(235, 241, 251, 0.96));
  text-align: left;
  border-color: rgba(209, 221, 240, 0.98);
}

.message-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #2d3c57;
  font-size: 15px;
  line-height: 1.6;
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(38, 53, 78, 0.42);
  animation: pulse 1.2s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.3s;
}

.info-card {
  margin-top: 10px;
  display: flex;
  gap: 10px;
  padding: 14px;
  border-radius: 18px;
}

.appointment-card {
  background: linear-gradient(135deg, rgba(227, 239, 255, 0.92), rgba(239, 246, 255, 0.96));
}

.qr-card {
  background: linear-gradient(135deg, rgba(246, 248, 252, 0.98), rgba(255, 255, 255, 0.98));
}

.info-card-icon {
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

.info-card-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.info-card-title {
  color: #1f2f49;
  font-size: 14px;
  font-weight: 700;
}

.info-card-line {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  color: #30425e;
  font-size: 13px;
  line-height: 1.55;
}

.info-label {
  color: rgba(48, 66, 94, 0.68);
}

.qr-image {
  width: 190px;
  max-width: 100%;
  margin-top: 8px;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 12px 28px rgba(37, 54, 79, 0.08);
}

.composer {
  width: var(--chat-shell-width);
  margin-top: 14px;
  padding: 0;
  background: transparent;
}

.composer-floating {
  flex: 0 0 auto;
}

.assistant-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.assistant-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.assistant-label {
  color: #31445f;
  font-size: 13px;
  font-weight: 700;
}

.assistant-tip {
  color: rgba(70, 84, 108, 0.78);
  font-size: 12px;
  line-height: 1.4;
}

.assistant-select {
  display: none;
}

.assistant-pills {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 70%;
}

.assistant-pill {
  border: 1px solid rgba(166, 181, 214, 0.75);
  border-radius: 999px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.92);
  color: #30425e;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
  box-shadow: 0 8px 18px rgba(53, 64, 92, 0.08);
}

.assistant-pill:hover {
  transform: translateY(-1px);
}

.assistant-pill.active {
  background: linear-gradient(135deg, rgba(97, 135, 255, 0.18), rgba(255, 255, 255, 0.98));
  border-color: rgba(91, 125, 248, 0.95);
  color: #20385f;
}

.composer-inner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(225, 232, 242, 0.96);
  box-shadow:
    0 18px 36px rgba(55, 68, 96, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.composer-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  min-height: 58px;
  padding: 0 18px;
  color: #26354e;
  font-size: 15px;
  border-radius: 16px;
  background: transparent;
  border: 0;
  box-shadow: none;
}

.composer-input::placeholder {
  color: rgba(38, 53, 78, 0.5);
}

.composer-send {
  border: 0;
  min-width: 52px;
  min-height: 52px;
  padding: 0;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(180deg, #adc2ff, #96aff8);
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 12px 24px rgba(120, 146, 221, 0.28);
}

.composer-send:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 28px rgba(120, 146, 221, 0.36);
}

.composer-send:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.composer-send-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 24px;
  line-height: 1;
  transform: translateY(-1px);
}

@keyframes onlinePulse {
  0% {
    box-shadow:
      0 0 0 0 rgba(53, 199, 89, 0.38),
      0 0 12px rgba(53, 199, 89, 0.32);
  }
  70% {
    box-shadow:
      0 0 0 10px rgba(53, 199, 89, 0),
      0 0 18px rgba(53, 199, 89, 0.22);
  }
  100% {
    box-shadow:
      0 0 0 0 rgba(53, 199, 89, 0),
      0 0 12px rgba(53, 199, 89, 0.18);
  }
}

@keyframes pulse {
  0%,
  80%,
  100% {
    transform: scale(0.72);
    opacity: 0.36;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (max-width: 900px) {
  .message-row {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .chat-shell {
    padding: 10px 10px 8px;
  }

  .chat-topbar {
    margin-bottom: 10px;
    padding: 12px 14px;
    border-radius: 18px;
  }

  .topbar-brand strong {
    font-size: 15px;
  }

  .brand-status-text {
    font-size: 11px;
  }

  .topbar-actions {
    gap: 14px;
  }

  .topbar-link {
    font-size: 14px;
  }

  .chat-panel {
    border-radius: 22px;
    width: 100%;
    height: calc(100vh - 154px);
  }

  .message-stream {
    padding: 14px 14px 10px;
  }

  .message-row {
    max-width: 100%;
  }

  .message-avatar {
    width: 32px;
    height: 32px;
    flex-basis: 32px;
  }

  .message-bubble {
    width: fit-content;
    max-width: calc(100% - 44px);
    padding: 10px 13px;
  }

  .message-row.is-user .message-bubble {
    max-width: calc(100% - 44px);
  }

  .message-text {
    font-size: 14px;
  }

  .composer {
    width: 100%;
    margin-top: 10px;
    padding-bottom: calc(4px + env(safe-area-inset-bottom));
  }

  .assistant-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .assistant-pills {
    max-width: 100%;
    justify-content: flex-start;
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: 2px;
  }

  .composer-inner {
    align-items: center;
    flex-direction: row;
    gap: 8px;
    padding: 8px;
    border-radius: 20px;
  }

  .composer-input {
    min-height: 48px;
    padding: 0 10px;
    border-radius: 16px;
  }

  .composer-send {
    width: auto;
    flex: 0 0 auto;
    min-width: 46px;
    min-height: 46px;
    border-radius: 999px;
  }

  .composer-send-icon {
    font-size: 20px;
  }
}
</style>
