import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import zhTW from './locales/zh-TW'
import en from './locales/en'
import ja from './locales/ja'
import ko from './locales/ko'
import fr from './locales/fr'
import es from './locales/es'
import ru from './locales/ru'
import { getAppStorageItem } from '@/utils/browserStorage'

// 获取浏览器语言或默认语言
function getDefaultLocale(): string {
  const savedLocale = getAppStorageItem('selectedLanguage')
  if (savedLocale) {
    return savedLocale
  }
  
  const browserLocale = navigator.language
  if (browserLocale.startsWith('zh')) {
    return 'zh-CN'
  }
  return 'en'
}

const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: getDefaultLocale(), // 默认语言
  fallbackLocale: 'zh-CN', // 回退语言
  messages: {
    'zh-CN': zhCN,
    'zh-TW': zhTW,
    'en': en,
    'ja': ja,
    'ko': ko,
    'fr': fr,
    'es': es,
    'ru': ru,
  },
})

export default i18n
