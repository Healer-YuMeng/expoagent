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

const SOURCE_STORAGE_KEY = 'ycis_channel_source';
const VISIT_FLAG_PREFIX = 'ycis_channel_visit_logged_';

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

export function shouldTrackVisit(slug: ChannelSlug): boolean {
  const key = `${VISIT_FLAG_PREFIX}${slug}`;
  if (sessionStorage.getItem(key)) {
    return false;
  }
  sessionStorage.setItem(key, '1');
  return true;
}

export function buildChannelUrl(base: string, slug: ChannelSlug): string {
  const trimmed = base.endsWith('/') ? base : `${base}/`;
  return `${trimmed}?source=${slug}`;
}
