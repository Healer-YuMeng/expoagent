export const AUTH_LOGIN_AT_KEY = 'ycis_login_at';
export const AUTH_SESSION_DURATION_MS = 12 * 60 * 60 * 1000;

export function parseSessionTimestamp(rawValue: string | null): number | null {
  if (!rawValue) {
    return null;
  }

  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export function isSessionExpired(loginAt: number | null, now = Date.now()): boolean {
  if (!loginAt) {
    return true;
  }
  return now - loginAt >= AUTH_SESSION_DURATION_MS;
}

export function resolvePostLoginPath(
  redirectPath: string | null | undefined,
  fallbackPath: string,
): string {
  if (!redirectPath) {
    return fallbackPath;
  }

  const trimmed = redirectPath.trim();
  if (!trimmed.startsWith('/') || trimmed.startsWith('//')) {
    return fallbackPath;
  }
  if (trimmed.startsWith('/auth/login')) {
    return fallbackPath;
  }
  return trimmed;
}
