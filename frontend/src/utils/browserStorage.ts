export function getAppStorageItem(key: string): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return localStorage.getItem(key);
}

export function setAppStorageItem(key: string, value: string) {
  if (typeof window === 'undefined') {
    return;
  }
  localStorage.setItem(key, value);
}

export function removeAppStorageItem(key: string) {
  if (typeof window === 'undefined') {
    return;
  }
  localStorage.removeItem(key);
}
