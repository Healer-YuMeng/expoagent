<template>
  <div class="settings-view">
    <TeacherPageHeader :title="t('settings.title')" />

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
import { useI18n } from 'vue-i18n';
import QRCode from 'qrcode';
import { CHANNELS, buildChannelUrl, buildStartChatEntryUrl, type ChannelSlug } from '@/utils/channelSource';
import { useAuthStore } from '@/stores/auth';
import { useFeatureGateBootstrap } from '@/composables/useFeatureGateBootstrap';
import TeacherPageHeader from '@/components/TeacherPageHeader.vue';

const { t } = useI18n();
useFeatureGateBootstrap();
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
