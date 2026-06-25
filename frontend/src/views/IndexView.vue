<template>
  <div class="landing-page">
    <PaintBackground />

    <div class="landing-shell">
      <div class="hero-copy">
        <h1 class="hero-title">
          <span class="hero-segment hero-segment-intro">我是</span>
          <span class="hero-segment hero-highlight">展会智能助手</span>
          <span class="hero-segment hero-segment-outro">，扫码直达聊天</span>
        </h1>
      </div>

      <div class="entry-stack">
        <button class="launcher" type="button" aria-label="点击聊天" @click="goToChat">
          <span class="launcher-text">点击聊天</span>
          <img src="/start.svg" alt="" class="launcher-arrow" aria-hidden="true" />
        </button>

        <div class="qr-card">
          <div class="qr-frame">
            <img v-if="qrCodeDataUrl" :src="qrCodeDataUrl" alt="扫码进入聊天" class="qr-image" />
          </div>
          <p class="qr-title">扫码进入聊天</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import QRCode from 'qrcode';
import PaintBackground from '@/components/PaintBackground.vue';
import { captureSourceFromQuery, shouldTrackVisit } from '@/utils/channelSource';
import { trackChannelVisit } from '@/api/channelMetrics';
import { getAppStorageItem } from '@/utils/browserStorage';

const PUBLIC_CHAT_URL = 'http://101.35.111.34:8606/?assistant_id=fea1734f-c2e5-4bd0-aadc-61b69a11d88b';

const router = useRouter();
const route = useRoute();
const { locale } = useI18n();
const qrCodeDataUrl = ref('');

function goToChat() {
  router.push({ name: 'StartChat', query: route.query });
}

onMounted(() => {
  QRCode.toDataURL(PUBLIC_CHAT_URL, {
    width: 220,
    margin: 1,
  })
    .then((dataUrl: string) => {
      qrCodeDataUrl.value = dataUrl;
    })
    .catch((error: unknown) => {
      console.warn('generate home qr code failed', error);
      qrCodeDataUrl.value = '';
    });

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

.entry-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.hero-copy {
  text-align: center;
  color: #23364d;
  text-shadow: 0 10px 30px rgba(248, 251, 255, 0.82);
}

.hero-title {
  margin: 0;
  font-size: clamp(40px, 5.1vw, 74px);
  line-height: 1.12;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.hero-segment {
  display: inline-block;
  opacity: 0;
  filter: blur(10px);
  transform: translateY(22px) scale(0.98);
  animation: revealText 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
}

.hero-segment-intro {
  animation-delay: 0.08s;
}

.hero-highlight {
  color: #4a78d1;
  animation-delay: 0.24s;
  text-shadow: 0 0 18px rgba(74, 120, 209, 0.18);
}

.hero-segment-outro {
  animation-delay: 0.42s;
}

.launcher {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-width: 192px;
  height: 84px;
  padding: 0 28px;
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

.launcher-text {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
}

.launcher:hover {
  transform: translateY(-2px) scale(1.01);
  border-color: rgba(126, 152, 189, 0.9);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    0 20px 38px rgba(83, 112, 149, 0.22);
}

.launcher-arrow {
  width: 34px;
  height: 34px;
}

.qr-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 18px 18px;
  border-radius: 26px;
  background: rgba(252, 253, 255, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 18px 34px rgba(83, 112, 149, 0.12);
  position: relative;
  overflow: hidden;
  opacity: 0;
  filter: blur(16px);
  transform: translateY(26px) scale(0.94);
  animation: revealQr 1.1s cubic-bezier(0.18, 0.82, 0.22, 1) 0.55s forwards;
}

.qr-card::before {
  content: '';
  position: absolute;
  inset: -20% -10%;
  background:
    radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.78), transparent 30%),
    radial-gradient(circle at 70% 78%, rgba(165, 189, 233, 0.26), transparent 32%);
  opacity: 0.85;
  pointer-events: none;
  animation: qrAura 6.4s ease-in-out 1.4s infinite;
}

.qr-frame {
  width: 176px;
  height: 176px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  border-radius: 22px;
  background: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.qr-image {
  width: 100%;
  height: 100%;
  display: block;
  border-radius: 14px;
  opacity: 0;
  transform: scale(0.92);
  filter: blur(8px);
  animation: revealQrImage 1s ease-out 0.95s forwards;
}

.qr-title {
  margin: 0;
  color: #23364d;
  font-size: 18px;
  font-weight: 700;
  position: relative;
  z-index: 1;
}

@keyframes revealText {
  0% {
    opacity: 0;
    filter: blur(10px);
    transform: translateY(22px) scale(0.98);
  }
  100% {
    opacity: 1;
    filter: blur(0);
    transform: translateY(0) scale(1);
  }
}

@keyframes revealQr {
  0% {
    opacity: 0;
    filter: blur(16px);
    transform: translateY(26px) scale(0.94);
  }
  100% {
    opacity: 1;
    filter: blur(0);
    transform: translateY(0) scale(1);
  }
}

@keyframes revealQrImage {
  0% {
    opacity: 0;
    transform: scale(0.92);
    filter: blur(8px);
  }
  100% {
    opacity: 1;
    transform: scale(1);
    filter: blur(0);
  }
}

@keyframes qrAura {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
    opacity: 0.7;
  }
  50% {
    transform: translate3d(1.5%, -2%, 0) scale(1.04);
    opacity: 1;
  }
}

@media (max-width: 768px) {
  .landing-shell {
    gap: 34px;
    padding: 24px 18px;
  }

  .hero-title {
    font-size: clamp(28px, 8.6vw, 42px);
    letter-spacing: 0.01em;
  }

  .launcher {
    min-width: 168px;
    height: 74px;
    padding: 0 22px;
  }

  .launcher-text {
    font-size: 18px;
  }

  .launcher-arrow {
    width: 28px;
    height: 28px;
  }

  .qr-card {
    padding: 14px;
    border-radius: 22px;
  }

  .qr-frame {
    width: 144px;
    height: 144px;
    border-radius: 18px;
  }

  .qr-title {
    font-size: 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-segment,
  .qr-card,
  .qr-image,
  .qr-card::before {
    animation: none;
    opacity: 1;
    filter: none;
    transform: none;
  }
}
</style>
