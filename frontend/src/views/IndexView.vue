<template>
  <div class="landing-page">
    <PaintBackground />

    <div class="landing-shell">
      <div class="hero-copy">
        <h1 class="hero-title">获客智能体</h1>
      </div>

      <button class="launcher" type="button" aria-label="进入对话" @click="goToChat">
        <img src="/start.svg" alt="" class="launcher-arrow" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import PaintBackground from '@/components/PaintBackground.vue';
import { captureSourceFromQuery, shouldTrackVisit } from '@/utils/channelSource';
import { trackChannelVisit } from '@/api/channelMetrics';
import { getAppStorageItem } from '@/utils/browserStorage';

const router = useRouter();
const route = useRoute();
const { locale } = useI18n();

function goToChat() {
  router.push({ name: 'StartChat', query: route.query });
}

onMounted(() => {
  const savedLocale = getAppStorageItem('selectedLanguage')
  if (savedLocale && locale.value !== savedLocale) {
    locale.value = savedLocale
  }
  const normalized = captureSourceFromQuery(route.query);
  if (normalized && shouldTrackVisit(normalized)) {
    trackChannelVisit(normalized).catch((err) => {
      console.warn('trackChannelVisit failed', err);
    });
  }
});
</script>

<style scoped>
.landing-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: #ffffff;
}

.landing-shell {
  position: relative;
  z-index: 10;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 34px;
  padding: 40px 24px;
}

.hero-copy {
  text-align: center;
  color: #23364d;
  text-shadow: 0 10px 30px rgba(248, 251, 255, 0.82);
}

.hero-title {
  margin: 0;
  font-size: clamp(52px, 6vw, 88px);
  line-height: 1.02;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.launcher {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 146px;
  height: 84px;
  padding: 0;
  border: 1px solid rgba(164, 184, 214, 0.7);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(253, 254, 255, 0.96), rgba(236, 242, 249, 0.9));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.94),
    0 18px 34px rgba(83, 112, 149, 0.16);
  color: #172231;
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}

.launcher:hover {
  transform: translateY(-2px) scale(1.01);
  border-color: rgba(126, 152, 189, 0.9);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    0 20px 38px rgba(83, 112, 149, 0.22);
}

.launcher-arrow {
  width: 44px;
  height: 44px;
}

@media (max-width: 768px) {
  .landing-shell {
    gap: 34px;
    padding: 24px 18px;
  }

  .hero-title {
    font-size: clamp(34px, 11vw, 52px);
    letter-spacing: 0.03em;
  }

  .launcher {
    min-width: 128px;
    height: 74px;
  }
}
</style>
