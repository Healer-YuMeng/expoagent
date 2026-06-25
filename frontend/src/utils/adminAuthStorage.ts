export const AUTH_TOKEN_KEY = 'ycis_token';
export const AUTH_USER_KEY = 'ycis_user';
export const AUTH_LOGIN_AT_KEY = 'ycis_login_at';

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

interface AdminAuthSnapshot {
  token: string | null;
  userJson: string | null;
  loginAt: string | null;
}

function readSnapshot(storage: StorageLike): AdminAuthSnapshot {
  return {
    token: storage.getItem(AUTH_TOKEN_KEY),
    userJson: storage.getItem(AUTH_USER_KEY),
    loginAt: storage.getItem(AUTH_LOGIN_AT_KEY),
  };
}

export function clearAdminAuthStorage(sessionStorageLike: StorageLike, localStorageLike: StorageLike) {
  sessionStorageLike.removeItem(AUTH_TOKEN_KEY);
  sessionStorageLike.removeItem(AUTH_USER_KEY);
  sessionStorageLike.removeItem(AUTH_LOGIN_AT_KEY);
  localStorageLike.removeItem(AUTH_TOKEN_KEY);
  localStorageLike.removeItem(AUTH_USER_KEY);
  localStorageLike.removeItem(AUTH_LOGIN_AT_KEY);
}

export function persistAdminAuthStorage(
  sessionStorageLike: StorageLike,
  localStorageLike: StorageLike,
  token: string,
  userJson: string,
  loginAt: number,
) {
  sessionStorageLike.setItem(AUTH_TOKEN_KEY, token);
  sessionStorageLike.setItem(AUTH_USER_KEY, userJson);
  sessionStorageLike.setItem(AUTH_LOGIN_AT_KEY, String(loginAt));
  localStorageLike.removeItem(AUTH_TOKEN_KEY);
  localStorageLike.removeItem(AUTH_USER_KEY);
  localStorageLike.removeItem(AUTH_LOGIN_AT_KEY);
}

export function loadAdminAuthStorage(
  sessionStorageLike: StorageLike,
  localStorageLike: StorageLike,
): AdminAuthSnapshot {
  const sessionSnapshot = readSnapshot(sessionStorageLike);
  if (sessionSnapshot.token && sessionSnapshot.userJson) {
    return sessionSnapshot;
  }

  const legacySnapshot = readSnapshot(localStorageLike);
  if (legacySnapshot.token && legacySnapshot.userJson) {
    persistAdminAuthStorage(
      sessionStorageLike,
      localStorageLike,
      legacySnapshot.token,
      legacySnapshot.userJson,
      Number(legacySnapshot.loginAt || Date.now()),
    );
    return readSnapshot(sessionStorageLike);
  }

  return sessionSnapshot;
}
