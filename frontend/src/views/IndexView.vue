<template>
  <div class="landing-page">
    <PaintBackground />

    <div class="landing-shell">
      <div class="hero-copy">
        <h1 class="hero-title">XX学校</h1>
        <h2 class="hero-subtitle">智能招生助手</h2>
      </div>

      <button
        class="launcher"
        type="button"
        :aria-label="currentPrompt"
        @click="showLanguageModal = true"
      >
        <img src="/start.svg" alt="" class="launcher-arrow" aria-hidden="true" />
      </button>
    </div>

    <Transition name="selector-fade">
      <div
        v-if="showLanguageModal"
        class="selector-overlay"
        @click="showLanguageModal = false"
      >
        <div class="selector-card" @click.stop>
          <div class="selector-header">
            <h3 class="selector-title">{{ currentPrompt }}</h3>
          </div>

          <div class="language-grid">
            <button
              v-for="lang in languages"
              :key="lang.code"
              class="language-tile"
              type="button"
              @click="selectLanguage(lang.code)"
            >
              <span class="tile-flag" aria-hidden="true">{{ lang.flag }}</span>
              <span class="tile-name">{{ lang.name }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import PaintBackground from '@/components/PaintBackground.vue';
import { captureSourceFromQuery, shouldTrackVisit } from '@/utils/channelSource';
import { trackChannelVisit } from '@/api/channelMetrics';
import { getAppStorageItem, setAppStorageItem } from '@/utils/browserStorage';

const router = useRouter();
const route = useRoute();
const { locale } = useI18n();

const showLanguageModal = ref(false);

const languageOptions = [
  { code: 'zh-CN', name: '简体中文', flag: '🇨🇳' },
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'zh-TW', name: '繁體中文', flag: '🇭🇰' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'ru', name: 'Русский', flag: '🇷🇺' },
];

const promptMap: Record<string, string> = {
  'zh-CN': '请选择您的语言',
  'zh-TW': '請選擇您的語言',
  en: 'Please select your language',
  ja: '言語を選択してください',
  ko: '언어를 선택해 주세요',
  fr: 'Veuillez choisir votre langue',
  es: 'Seleccione su idioma',
  ru: 'Пожалуйста, выберите язык',
};

const currentPrompt = computed(() => promptMap[locale.value] || promptMap.en);

const languages = computed(() => {
  const current = languageOptions.find((lang) => lang.code === locale.value);
  if (!current) {
    return languageOptions;
  }
  return [current, ...languageOptions.filter((lang) => lang.code !== locale.value)];
});

function selectLanguage(langCode: string) {
  setAppStorageItem('selectedLanguage', langCode);
  locale.value = langCode;
  showLanguageModal.value = false;
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
  gap: 26px;
  padding: 40px 24px;
}

.hero-copy {
  text-align: center;
  color: #2f415b;
  text-shadow: 0 4px 18px rgba(255, 255, 255, 0.55);
}

.hero-title,
.hero-subtitle {
  margin: 0;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.hero-title {
  font-size: clamp(46px, 5.2vw, 76px);
  line-height: 1.05;
}

.hero-subtitle {
  margin-top: 20px;
  font-size: clamp(50px, 5.8vw, 84px);
  line-height: 1.04;
}

.launcher {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 146px;
  height: 84px;
  padding: 0;
  border: 2px solid rgba(176, 157, 177, 0.85);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(244, 235, 242, 0.88));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 8px 18px rgba(88, 70, 101, 0.18);
  color: #171717;
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.launcher:hover {
  transform: translateY(-2px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 14px 26px rgba(88, 70, 101, 0.24);
}

.launcher-arrow {
  width: 44px;
  height: 44px;
}

.selector-overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(96, 93, 102, 0.18);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.selector-card {
  width: min(100%, 560px);
  max-height: min(88vh, 760px);
  border-radius: 28px;
  padding: 26px 28px 30px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(246, 246, 247, 0.94));
  border: 1px solid rgba(255, 255, 255, 0.94);
  box-shadow: 0 30px 70px rgba(31, 31, 42, 0.24);
  overflow-y: auto;
}

.selector-header {
  margin-bottom: 18px;
  text-align: center;
}

.selector-title {
  margin: 0;
  color: #283950;
  font-size: clamp(22px, 2.6vw, 30px);
  font-weight: 700;
}

.language-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.language-tile {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 58px;
  padding: 0 18px;
  border: 1px solid rgba(219, 224, 233, 0.96);
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff, #fbfbfc);
  color: #2d3c58;
  box-shadow: 0 2px 0 rgba(231, 234, 239, 0.95);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.language-tile:hover {
  transform: translateY(-1px);
  border-color: rgba(185, 194, 212, 0.98);
  box-shadow: 0 12px 24px rgba(31, 40, 60, 0.08);
}

.tile-flag {
  font-size: 24px;
  line-height: 1;
}

.tile-name {
  font-size: 15px;
  font-weight: 600;
}

.selector-fade-enter-active,
.selector-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.selector-fade-enter-from,
.selector-fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

@media (max-width: 768px) {
  .landing-shell {
    gap: 34px;
    padding: 24px 18px;
  }

  .hero-title {
    font-size: clamp(34px, 9.5vw, 50px);
  }

  .hero-subtitle {
    margin-top: 18px;
    font-size: clamp(39px, 10.5vw, 56px);
  }

  .launcher {
    min-width: 128px;
    height: 74px;
  }

  .selector-card {
    width: min(100%, 420px);
    max-height: min(92vh, 680px);
    padding: 22px 18px 18px;
    border-radius: 24px;
  }

  .language-grid {
    grid-template-columns: 1fr;
  }

  .selector-title {
    font-size: 20px;
  }

  .language-tile {
    min-height: 52px;
    padding: 0 16px;
  }

  .tile-flag {
    font-size: 22px;
  }

  .tile-name {
    font-size: 14px;
  }
}
</style>
