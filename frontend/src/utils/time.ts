const EXPLICIT_TIMEZONE_PATTERN = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;
const PLAIN_DATE_TIME_PATTERN =
  /^(\d{4})[-/](\d{2})[-/](\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/;

export function formatChinaDateTime(
  value?: string | Date | null,
  fallback = '',
): string {
  if (!value) {
    return fallback;
  }

  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      return fallback;
    }
    return formatDateInShanghai(value);
  }

  const text = value.trim();
  if (!text) {
    return fallback;
  }

  const plainDateTimeMatch = text.match(PLAIN_DATE_TIME_PATTERN);
  if (plainDateTimeMatch && !EXPLICIT_TIMEZONE_PATTERN.test(text)) {
    const [, year, month, day, hour = '00', minute = '00', second = '00'] = plainDateTimeMatch;
    return `${year}/${month}/${day} ${hour}:${minute}:${second}`;
  }

  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return text;
  }

  return formatDateInShanghai(parsed);
}

function formatDateInShanghai(date: Date): string {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);

  const getPart = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? '';

  return `${getPart('year')}/${getPart('month')}/${getPart('day')} ${getPart('hour')}:${getPart('minute')}:${getPart('second')}`;
}
