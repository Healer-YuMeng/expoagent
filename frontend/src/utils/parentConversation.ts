import { getAppStorageItem, removeAppStorageItem, setAppStorageItem } from '@/utils/browserStorage';

const LAST_PARENT_CONVERSATION_ID_KEY = 'ycis_last_parent_conversation_id';

export function persistLastParentConversationId(conversationId: string) {
  const normalized = conversationId.trim();
  if (!normalized) {
    return;
  }
  setAppStorageItem(LAST_PARENT_CONVERSATION_ID_KEY, normalized);
}

export function getPersistedLastParentConversationId(): string | null {
  const stored = getAppStorageItem(LAST_PARENT_CONVERSATION_ID_KEY)?.trim();
  return stored || null;
}

export function clearPersistedLastParentConversationId() {
  removeAppStorageItem(LAST_PARENT_CONVERSATION_ID_KEY);
}
