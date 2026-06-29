export type ChannelSlug = 'xhs' | 'dy' | 'blbl' | 'wb' | 'gzh' | 'wxsp';

export interface ChannelInfo {
  slug: ChannelSlug;
  name: string;
  description: string;
}

export const CHANNELS: ChannelInfo[] = [
  { slug: 'xhs', name: '小红书', description: 'Lifestyle 内容渠道' },
  { slug: 'dy', name: '抖音', description: '短视频渠道' },
  { slug: 'blbl', name: '哔哩哔哩', description: '二次元/教育社区' },
  { slug: 'wb', name: '微博', description: '社交话题渠道' },
  { slug: 'gzh', name: '微信公众号', description: '长图文推送' },
  { slug: 'wxsp', name: '微信视频号', description: '微信生态短视频' },
];

const START_CHAT_PATH = '/start-chat';
const SOURCE_STORAGE_KEY = 'ycis_channel_source';

function isAbsoluteUrl(value: string): boolean {
  return /^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(value);
}

function getUrlParts(base: string) {
  const trimmed = base.trim() || '/';
  const absolute = isAbsoluteUrl(trimmed);
  const url = absolute ? new URL(trimmed) : new URL(trimmed, 'http://placeholder.local');

  if (url.pathname === '/' || url.pathname === '') {
    url.pathname = START_CHAT_PATH;
  }

  return { absolute, url };
}

export function normalizeChannelSource(raw?: string | null): ChannelSlug | null {
  if (!raw) return null;
  const value = raw.trim().toLowerCase();
  if (CHANNELS.some((item) => item.slug === value)) {
    return value as ChannelSlug;
  }
  return null;
}

export function persistChannelSource(slug: ChannelSlug) {
  sessionStorage.setItem(SOURCE_STORAGE_KEY, slug);
}

export function captureSourceFromQuery(query: Record<string, unknown>): ChannelSlug | null {
  const raw = query?.source;
  if (typeof raw === 'string') {
    const normalized = normalizeChannelSource(raw);
    if (normalized) {
      persistChannelSource(normalized);
      return normalized;
    }
  }
  return null;
}

export function getPersistedChannelSource(): ChannelSlug | null {
  const stored = sessionStorage.getItem(SOURCE_STORAGE_KEY);
  return normalizeChannelSource(stored);
}

export function buildStartChatEntryUrl(base: string, params: Record<string, string> = {}): string {
  const { absolute, url } = getUrlParts(base);
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      url.searchParams.set(key, value);
    }
  });
  return absolute ? url.toString() : `${url.pathname}${url.search}`;
}

export function buildChannelUrl(base: string, slug: ChannelSlug): string {
  return buildStartChatEntryUrl(base, { source: slug });
}
