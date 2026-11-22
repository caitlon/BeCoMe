/**
 * Whether the first client render has to reproduce server-rendered HTML.
 *
 * The prerendered pages are English, signed out and in the default theme, so a
 * component that reads browser state (a stored theme, the system colour scheme)
 * must start from what the server saw while this is true, then correct itself
 * inside startTransition. The client entry sets the flag right before
 * hydrateRoot; nothing sets it on the plain createRoot path, which keeps its
 * current behavior.
 */
let hydrating = false;

export function isHydrating(): boolean {
  return hydrating;
}

export function setHydrating(value: boolean): void {
  hydrating = value;
}
