// The sessionStorage key of an assistant conversation, and the removal of one project's
// conversation. Kept apart from useAssistantChat.ts on purpose: pages in the main bundle
// (the project page and the project list) reach the removal through the gated hook
// useForgetAssistantProject in components/assistant/index.tsx, and useAssistantChat belongs
// to the lazy assistant chunk, which a build without VITE_ASSISTANT_ENABLED must not contain.
// Nothing assistant-specific (API paths, locale strings) may be imported here.

export const STORAGE_BASE = "assistant-chat";
/**
 * sessionStorage keys are `${STORAGE_PREFIX}:${userId}:${projectId ?? "general"}`. The
 * version is bumped when the stored shape changes, e.g. SourceRef; a key of an older
 * version is never read, and sign-out still removes it.
 */
export const STORAGE_PREFIX = `${STORAGE_BASE}:v1`;

// Bumped per key by removeAssistantProjectHistory(). A thread remembers the value of its
// key it was loaded under and stops writing once that value is out of date, so a removal
// cannot be undone by a thread that is still mounted for that project (the panel keeps the
// project it was opened for while the page navigates away).
const keyGenerations = new Map<string, number>();

export function storageKeyFor(userId: string, projectId: string | null): string {
  return `${STORAGE_PREFIX}:${userId}:${projectId ?? "general"}`;
}

export function generationOf(key: string): number {
  return keyGenerations.get(key) ?? 0;
}

/** Removes one project's conversation of one user, for leaving or deleting the project. */
export function removeAssistantProjectHistory(userId: string, projectId: string): void {
  const key = storageKeyFor(userId, projectId);
  keyGenerations.set(key, generationOf(key) + 1);
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Nothing was stored that could be removed.
  }
}
