<template>
  <div class="settings-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">⚙️ {{ t('settings.title') }}</h1>
      <button class="refresh-btn glass" @click="fetchWelcomeMessage" :disabled="loading">
        <span class="btn-icon">🔄</span>
        <span>{{ t('settings.refresh') }}</span>
      </button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-alert glass">
      <div class="error-icon">⚠️</div>
      <div class="error-text">{{ error }}</div>
    </div>

    <!-- 设置表单 -->
    <div class="settings-section glass">
      <div class="section-title">💬 {{ t('settings.welcomeMessageTitle') }}</div>
      <div class="section-description">
        {{ t('settings.welcomeMessageDesc') }}
      </div>
      
      <!-- AI翻译按钮 -->
      <div class="ai-translate-section">
        <div class="translate-hint">
          <span class="hint-icon">🤖</span>
          <span>{{ t('settings.aiTranslateHint') }}</span>
        </div>
        <button
          class="translate-btn glass"
          :class="{ loading: translating }"
          :disabled="translating || !welcomeMessages['zh-CN']?.trim()"
          @click="handleAITranslate"
        >
          <span v-if="!translating" class="btn-icon">🌐</span>
          <span v-if="translating" class="loader"></span>
          <span>{{ translating ? t('settings.translating') : t('settings.aiTranslateButton') }}</span>
        </button>
      </div>

      <!-- 多语言标签页 -->
      <div class="language-tabs">
        <button
          v-for="lang in languages"
          :key="lang.code"
          class="tab-btn"
          :class="{ active: currentLanguage === lang.code }"
          @click="currentLanguage = lang.code"
        >
          <span class="tab-flag">{{ lang.flag }}</span>
          <span class="tab-name">{{ lang.name }}</span>
        </button>
      </div>

      <!-- 当前语言的输入框 -->
      <div class="language-input-section">
        <div class="language-label">
          <span class="label-icon">✏️</span>
          <span>{{ getCurrentLanguageName() }}</span>
        </div>
        <textarea
          v-model="welcomeMessages[currentLanguage]"
          class="form-textarea"
          rows="10"
          :placeholder="getPlaceholderForLanguage(currentLanguage)"
        ></textarea>
      </div>
      
      <div class="form-hint">
        <span class="hint-icon">💡</span>
        <span>{{ t('settings.hint') }}</span>
      </div>

      <button
        class="save-btn"
        :class="{ loading: saving }"
        :disabled="saving"
        @click="handleSave"
      >
        <span v-if="!saving" class="btn-icon">💾</span>
        <span v-if="saving" class="loader"></span>
        <span>{{ saving ? t('settings.saving') : t('settings.saveButton') }}</span>
      </button>
    </div>

    <div class="settings-section glass">
      <div class="section-title">📱 {{ t('settings.channelQrTitle') }}</div>
      <div class="section-description">
        {{ t('settings.channelQrDesc') }}
      </div>

      <div class="base-url-row">
        <label>{{ t('settings.channelBaseUrl') }}</label>
        <el-input v-model="qrBaseUrl" :disabled="generatingQrs" size="large" />
      </div>
      <p class="section-description subtle">{{ t('settings.channelBaseHint') }}</p>

      <div class="qr-controls">
        <span>{{ t('settings.channelListHint') }}</span>
        <el-button size="small" @click="refreshAllQrs" :loading="generatingQrs">
          {{ t('settings.channelRegenerate') }}
        </el-button>
      </div>

      <div class="qr-grid">
        <div v-for="channel in channels" :key="channel.slug" class="qr-card">
          <div class="qr-card-header">
            <div>
              <h3>{{ getChannelLabel(channel.slug) }}</h3>
              <p>{{ getChannelDescription(channel.slug) }}</p>
            </div>
            <div class="qr-chip">{{ channel.slug.toUpperCase() }}</div>
          </div>
          <div class="qr-preview" v-if="qrPreviews[channel.slug]?.dataUrl">
            <img :src="qrPreviews[channel.slug]?.dataUrl || ''" alt="QR Code" />
          </div>
          <div class="qr-preview placeholder" v-else>
            <span>QR</span>
          </div>
          <p class="qr-link" @click="copyChannelLink(channel.slug)">
            {{ qrPreviews[channel.slug]?.url || buildChannelUrl(qrBaseUrl, channel.slug) }}
          </p>
          <div class="qr-actions">
            <button class="action-btn" @click="copyChannelLink(channel.slug)">{{ t('settings.copyLink') }}</button>
            <button class="action-btn" @click="downloadQr(channel.slug)">{{ t('settings.downloadQr') }}</button>
          </div>
          <p class="qr-note">{{ t('settings.channelBackendTodo') }}</p>
        </div>
      </div>
    </div>

    <div class="settings-section glass" v-if="authStore.userRole === 'admin' || authStore.userRole === 'super_admin'">
      <div class="section-title">🎫 {{ t('settings.parentEntryTitle') }}</div>
      <div class="section-description">
        {{ t('settings.parentEntryDesc') }}
      </div>
      <div class="parent-entry">
        <code>{{ parentEntryUrl }}</code>
        <el-button size="small" @click="copyParentLink">
          {{ t('settings.copyLink') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import { ElMessage } from 'element-plus';
import type { AxiosError } from 'axios';
import { getWelcomeMessage, updateWelcomeMessage, translateWelcomeMessage } from '@/api/teacher';
import { useI18n } from 'vue-i18n';
import QRCode from 'qrcode';
import { CHANNELS, buildChannelUrl, buildStartChatEntryUrl, type ChannelSlug } from '@/utils/channelSource';
import { useAuthStore } from '@/stores/auth';
import { useFeatureGateBootstrap } from '@/composables/useFeatureGateBootstrap';

const { t } = useI18n();
useFeatureGateBootstrap();

// 多语言配置
const languages = [
  { code: 'zh-CN', name: '简体中文', flag: '🇨🇳' },
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'zh-TW', name: '繁體中文', flag: '🇹🇼' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'ru', name: 'Русский', flag: '🇷🇺' },
];

// 状态
const welcomeMessages = ref<Record<string, string>>({});
const currentLanguage = ref('zh-CN');
const loading = ref(false);
const saving = ref(false);
const translating = ref(false);
const error = ref<string | null>(null);
const channels = CHANNELS; // TODO: replace with backend-provided channel list when API is ready
const qrBaseUrl = ref<string>(window.location.origin);
const qrPreviews = ref<Partial<Record<ChannelSlug, { url: string; dataUrl: string | null }>>>({});
const generatingQrs = ref(false);
const channelLabelMap: Record<ChannelSlug, string> = {
  xhs: 'dashboard.sources.xiaohongshu',
  dy: 'dashboard.sources.douyin',
  blbl: 'dashboard.sources.bilibili',
  wb: 'dashboard.sources.weibo',
  gzh: 'dashboard.sources.wechatOfficialAccount',
  wxsp: 'dashboard.sources.wechatVideo',
};

function resolveRequestErrorMessage(err: unknown, fallback: string): string {
  const axiosError = err as AxiosError<{ detail?: string }>;
  return axiosError?.response?.data?.detail || fallback;
}

function resolveLanguageName(code: string): string {
  return languages.find((lang) => lang.code === code)?.name || code;
}

// 获取当前语言的名称
const getCurrentLanguageName = () => {
  const lang = languages.find((l) => l.code === currentLanguage.value);
  return lang ? lang.name : currentLanguage.value;
};

// 获取每个语言的占位符文本
const getPlaceholderForLanguage = (langCode: string): string => {
  const placeholders: Record<string, string> = {
    'zh-CN': '请输入简体中文欢迎语...',
    'zh-TW': '請輸入繁體中文歡迎語...',
    'en': 'Enter welcome message in English...',
    'ja': '日本語でウェルカムメッセージを入力してください...',
    'ko': '한국어로 환영 메시지를 입력하세요...',
    'fr': 'Entrez le message de bienvenue en français...',
    'es': 'Ingrese el mensaje de bienvenida en español...',
    'ru': 'Введите приветственное сообщение на русском...',
  };
  return placeholders[langCode] || `Enter welcome message in ${langCode}...`;
};

// 获取欢迎语
const fetchWelcomeMessage = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await getWelcomeMessage();
    welcomeMessages.value = response.messages || {};
    
    // 确保所有语言都有初始值（避免undefined）
    languages.forEach((lang) => {
      if (!welcomeMessages.value[lang.code]) {
        welcomeMessages.value[lang.code] = '';
      }
    });
  } catch (err) {
    console.error(err);
    error.value = t('settings.errorLoad');
  } finally {
    loading.value = false;
  }
};

// AI自动翻译
const handleAITranslate = async () => {
  const sourceText = welcomeMessages.value['zh-CN']?.trim();
  if (!sourceText) {
    ElMessage.warning(t('settings.emptySourceWarning'));
    return;
  }

  translating.value = true;
  try {
    const response = await translateWelcomeMessage({
      source_text: sourceText,
      source_lang: 'zh-CN',
    });

    const translatedMessages: Record<string, string> = {
      'zh-CN': sourceText,
    };
    languages.forEach((lang) => {
      if (lang.code !== 'zh-CN') {
        translatedMessages[lang.code] = '';
      }
    });
    Object.assign(translatedMessages, response.translations || {});
    welcomeMessages.value = {
      ...welcomeMessages.value,
      ...translatedMessages,
    };

    if (response.failed_languages?.length) {
      const failedNames = response.failed_languages.map(resolveLanguageName).join('、');
      ElMessage.warning(`以下语言翻译失败：${failedNames}`);
    } else {
      ElMessage.success(t('settings.translateSuccess'));
    }
  } catch (err) {
    console.error(err);
    ElMessage.error(resolveRequestErrorMessage(err, t('settings.translateError')));
  } finally {
    translating.value = false;
  }
};

// 保存设置
const handleSave = async () => {
  // 检查至少有一个语言有内容
  const hasContent = Object.values(welcomeMessages.value).some((msg) => msg?.trim());
  if (!hasContent) {
    ElMessage.warning(t('settings.emptyWarning'));
    return;
  }

  saving.value = true;
  try {
    const response = await updateWelcomeMessage({ messages: welcomeMessages.value });
    welcomeMessages.value = response.messages;
    ElMessage.success(t('settings.saveSuccess'));
  } catch (err) {
    console.error(err);
    ElMessage.error(resolveRequestErrorMessage(err, t('settings.saveError')));
  } finally {
    saving.value = false;
  }
};

const generateQrForChannel = async (slug: ChannelSlug) => {
  const url = buildChannelUrl(qrBaseUrl.value, slug);
  try {
    const dataUrl = await QRCode.toDataURL(url, { width: 220 });
    qrPreviews.value[slug] = { url, dataUrl };
  } catch (error) {
    console.warn('generateQrForChannel', error);
    qrPreviews.value[slug] = { url, dataUrl: null };
  }
};

const refreshAllQrs = async () => {
  generatingQrs.value = true;
  try {
    await Promise.all(channels.map((channel) => generateQrForChannel(channel.slug)));
  } finally {
    generatingQrs.value = false;
  }
};

const copyChannelLink = async (slug: ChannelSlug) => {
  const preview = qrPreviews.value[slug];
  const link = preview?.url || buildChannelUrl(qrBaseUrl.value, slug);
  try {
    await navigator.clipboard.writeText(link);
    ElMessage.success(t('settings.copySuccess'));
  } catch (error) {
    console.warn('copyChannelLink', error);
    ElMessage.error(t('settings.copyError'));
  }
};

const downloadQr = (slug: ChannelSlug) => {
  const dataUrl = qrPreviews.value[slug]?.dataUrl;
  if (!dataUrl) {
    ElMessage.warning(t('settings.qrMissing'));
    return;
  }
  const link = document.createElement('a');
  link.href = dataUrl;
  link.download = `${slug}-qr.png`;
  link.click();
};

const getChannelLabel = (slug: ChannelSlug) => t(channelLabelMap[slug] ?? slug);
const getChannelDescription = (slug: ChannelSlug) => t(`settings.channelDescriptions.${slug}`);

const authStore = useAuthStore();
const parentEntryUrl = computed(() => {
  const schoolId = authStore.user?.school_id || '';
  return buildStartChatEntryUrl(qrBaseUrl.value, schoolId ? { school_id: schoolId } : {});
});

const copyParentLink = async () => {
  try {
    await navigator.clipboard.writeText(parentEntryUrl.value);
    ElMessage.success(t('settings.copySuccess'));
  } catch (e) {
    try {
      const el = document.createElement('textarea');
      el.value = parentEntryUrl.value;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      ElMessage.success(t('settings.copySuccess'));
    } catch (err) {
      ElMessage.error(t('settings.copyError'));
    }
  }
};

watch(() => qrBaseUrl.value, () => {
  refreshAllQrs();
});

onMounted(() => {
  void fetchWelcomeMessage();
  void refreshAllQrs();
});
</script>

<style scoped>
.settings-view {
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

/* 页面标题 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  color: #2c3e50;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.4);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
  font-size: 16px;
}

/* 错误提示 */
.error-alert {
  margin-bottom: 20px;
  padding: 20px 25px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  gap: 15px;
  border-left: 4px solid #e74c3c;
}

.error-icon {
  font-size: 24px;
}

.error-text {
  color: #c0392b;
  font-weight: 500;
  flex: 1;
}

/* 设置区域 */
.settings-section {
  padding: 35px;
  border-radius: 20px;
  margin-bottom: 25px;
}

.base-url-row {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}

.base-url-row label {
  min-width: 140px;
  font-weight: 600;
}

.qr-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
  font-size: 14px;
}

.qr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
}

.qr-card {
  border: 1px solid rgba(44, 62, 80, 0.08);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.qr-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.qr-chip {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(52, 152, 219, 0.15);
  font-weight: 600;
  font-size: 13px;
}

.qr-preview {
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 12px;
  border: 1px dashed rgba(44, 62, 80, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(44, 62, 80, 0.02);
}

.qr-preview img {
  max-width: 100%;
  max-height: 100%;
}

.qr-preview.placeholder span {
  color: rgba(44, 62, 80, 0.4);
}

.qr-link {
  font-size: 13px;
  word-break: break-all;
  color: rgba(44, 62, 80, 0.8);
  cursor: pointer;
}

.qr-actions {
  display: flex;
  gap: 10px;
}

.qr-actions .action-btn {
  flex: 1;
  border: none;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  background: rgba(52, 152, 219, 0.12);
  color: #2980b9;
  font-weight: 600;
}

.qr-note {
  font-size: 12px;
  color: rgba(44, 62, 80, 0.6);
}

.parent-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(44, 62, 80, 0.05);
  padding: 12px;
  border-radius: 10px;
  word-break: break-all;
}

code {
  background: transparent;
  color: #2c3e50;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 10px;
}

.section-description {
  font-size: 14px;
  color: rgba(44, 62, 80, 0.7);
  margin-bottom: 25px;
  line-height: 1.6;
}

.section-description.subtle {
  margin-top: 6px;
  font-size: 13px;
  color: rgba(44, 62, 80, 0.6);
}

.form-textarea {
  width: 100%;
  padding: 18px 20px;
  border-radius: 15px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  font-size: 15px;
  color: #2c3e50;
  font-family: inherit;
  line-height: 1.6;
  resize: vertical;
  transition: all 0.3s ease;
}

.form-textarea:focus {
  outline: none;
  border-color: rgba(52, 152, 219, 0.6);
  background: rgba(255, 255, 255, 0.4);
  box-shadow: 0 4px 20px rgba(52, 152, 219, 0.2);
}

.form-textarea::placeholder {
  color: rgba(44, 62, 80, 0.5);
}

.form-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  margin-bottom: 25px;
  font-size: 13px;
  color: rgba(44, 62, 80, 0.6);
}

.hint-icon {
  font-size: 16px;
}

.save-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 32px;
  border-radius: 15px;
  border: none;
  background: linear-gradient(135deg, #27ae60, #229954);
  color: white;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.save-btn:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow: 0 8px 25px rgba(39, 174, 96, 0.4);
}

.save-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.save-btn.loading {
  background: linear-gradient(135deg, #95a5a6, #7f8c8d);
}

/* 加载动画 */
.loader {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* AI翻译区域 */
.ai-translate-section {
  margin: 25px 0;
  padding: 20px;
  background: rgba(52, 152, 219, 0.05);
  border-radius: 12px;
  border: 2px dashed rgba(52, 152, 219, 0.3);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}

.translate-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: rgba(44, 62, 80, 0.7);
  flex: 1;
}

.translate-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #3498db, #2980b9);
  color: white;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.translate-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4);
}

.translate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.translate-btn.loading {
  background: linear-gradient(135deg, #95a5a6, #7f8c8d);
}

/* 语言标签页 */
.language-tabs {
  display: flex;
  gap: 8px;
  margin: 20px 0;
  flex-wrap: wrap;
  padding: 15px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 10px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  color: #2c3e50;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.6);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.tab-btn.active {
  background: linear-gradient(135deg, rgba(52, 152, 219, 0.9), rgba(41, 128, 185, 0.9));
  color: white;
  border-color: rgba(52, 152, 219, 0.6);
  box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
}

.tab-flag {
  font-size: 20px;
}

.tab-name {
  font-size: 13px;
}

/* 语言输入区域 */
.language-input-section {
  margin: 20px 0;
}

.language-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
}

.label-icon {
  font-size: 18px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
  }

  .page-title {
    font-size: 24px;
  }

  .refresh-btn {
    width: 100%;
    justify-content: center;
  }

  .settings-section {
    padding: 25px 20px;
  }

  .ai-translate-section {
    flex-direction: column;
    align-items: stretch;
  }

  .translate-btn {
    width: 100%;
    justify-content: center;
  }

  .language-tabs {
    gap: 6px;
    padding: 12px;
  }

  .tab-btn {
    padding: 8px 12px;
    font-size: 13px;
  }

  .tab-flag {
    font-size: 18px;
  }

  .form-textarea {
    padding: 15px;
    font-size: 14px;
  }

  .save-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
