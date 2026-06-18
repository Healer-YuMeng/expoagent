<template>
  <div class="chat-page">
    <PaintBackground />

    <div class="chat-shell">
      <header class="chat-topbar">
        <div class="topbar-brand">
          <strong>{{ t('chat.title') }}</strong>
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
        <section class="chat-heading">
          <h1>{{ t('chat.myConsultation') }}</h1>
          <p>{{ t('chat.subtitle') }}</p>
        </section>

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

        <footer class="composer">
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
              :disabled="isSending"
              @click="handleSendMessage"
            >
              {{ isSending ? t('common.sending') : t('common.send') }}
            </button>
          </div>
        </footer>
      </main>
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
  --chat-shell-width: min(100%, 1240px);
  position: relative;
  z-index: 10;
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 46px 22px 22px;
  box-sizing: border-box;
}

.chat-topbar {
  width: var(--chat-shell-width);
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22px;
  padding: 21px 40px;
  border-radius: 999px;
  background: rgba(246, 248, 255, 0.28);
  border: 1px solid rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 18px 42px rgba(53, 62, 93, 0.12);
}

.topbar-link {
  border: 0;
  background: transparent;
  color: rgba(48, 63, 90, 0.88);
  font-size: 17px;
  font-weight: 600;
  cursor: pointer;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 34px;
}

.topbar-brand {
  color: #334560;
}

.topbar-brand strong {
  font-size: 20px;
  font-weight: 700;
}

.chat-panel {
  width: var(--chat-shell-width);
  flex: 0 0 auto;
  min-height: 0;
  height: min(820px, calc(100vh - 160px));
  display: flex;
  flex-direction: column;
  border-radius: 34px;
  background: linear-gradient(180deg, rgba(244, 247, 255, 0.46), rgba(241, 222, 233, 0.36));
  border: 1px solid rgba(255, 255, 255, 0.58);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 26px 64px rgba(52, 57, 77, 0.14);
  overflow: hidden;
}

.chat-heading {
  padding: 28px 34px 22px;
  background: rgba(246, 248, 255, 0.32);
  border-bottom: 1px solid rgba(224, 229, 240, 0.86);
}

.chat-heading h1 {
  margin: 0 0 8px;
  color: #31445f;
  font-size: 22px;
  font-weight: 700;
}

.chat-heading p {
  margin: 0;
  color: rgba(70, 84, 108, 0.8);
  font-size: 14px;
}

.message-stream {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 28px 34px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: linear-gradient(180deg, rgba(214, 223, 244, 0.24), rgba(228, 194, 213, 0.24));
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
  gap: 14px;
  width: 100%;
  max-width: none;
}

.message-row.is-user {
  flex-direction: row-reverse;
  justify-content: flex-start;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  flex: 0 0 40px;
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
  font-size: 19px;
  line-height: 1;
}

.message-bubble {
  flex: 0 0 auto;
  width: fit-content;
  min-width: 0;
  max-width: min(68%, 840px);
  padding: 14px 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 26px rgba(53, 64, 92, 0.07);
  border: 1px solid rgba(236, 239, 245, 0.96);
}

.message-row.is-bot .message-bubble {
  text-align: left;
}

.message-row.is-user .message-bubble {
  background: rgba(255, 255, 255, 0.9);
  text-align: left;
}

.message-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #2d3c57;
  font-size: 17px;
  line-height: 1.58;
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
  padding: 22px 34px 26px;
  border-top: 1px solid rgba(224, 229, 240, 0.86);
  background: rgba(248, 243, 247, 0.28);
}

.assistant-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
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
  gap: 10px;
  max-width: 70%;
}

.assistant-pill {
  border: 1px solid rgba(166, 181, 214, 0.75);
  border-radius: 999px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.92);
  color: #30425e;
  font-size: 14px;
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
  gap: 18px;
}

.composer-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  min-height: 54px;
  padding: 0 24px;
  color: #26354e;
  font-size: 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(232, 236, 243, 0.96);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.composer-input::placeholder {
  color: rgba(38, 53, 78, 0.5);
}

.composer-send {
  border: 1px solid rgba(198, 204, 217, 0.9);
  min-width: 112px;
  min-height: 56px;
  padding: 0 24px;
  border-radius: 999px;
  color: #2b3d57;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 243, 248, 0.96));
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 8px 20px rgba(58, 70, 94, 0.08);
}

.composer-send:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(58, 70, 94, 0.12);
}

.composer-send:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
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
    padding: 18px 14px 14px;
  }

  .chat-topbar {
    padding: 16px 20px;
    border-radius: 22px;
  }

  .topbar-brand strong {
    font-size: 16px;
  }

  .topbar-actions {
    gap: 18px;
  }

  .chat-panel {
    border-radius: 24px;
    width: 100%;
    height: calc(100vh - 122px);
  }

  .chat-heading {
    padding: 22px 20px 18px;
  }

  .chat-heading h1 {
    font-size: 20px;
  }

  .message-stream {
    padding: 22px 20px;
  }

  .message-row {
    max-width: 100%;
  }

  .message-bubble {
    width: fit-content;
    max-width: calc(100% - 62px);
    padding: 12px 15px;
  }

  .message-row.is-user .message-bubble {
    max-width: calc(100% - 62px);
  }

  .composer {
    padding: 18px 20px 22px;
  }

  .assistant-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .assistant-pills {
    max-width: 100%;
    justify-content: flex-start;
  }

  .composer-inner {
    align-items: center;
    flex-direction: row;
    gap: 12px;
  }

  .composer-input {
    min-height: 52px;
    padding: 0 18px;
  }

  .composer-send {
    width: auto;
    flex: 0 0 auto;
    min-width: 96px;
    min-height: 52px;
    padding: 0 18px;
  }
}
</style>
