import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface AssistantUIValue {
  readonly isAvailable: boolean;
  readonly isOpen: boolean;
  /** The project the panel was last opened for (it stays after a close); null for the general panel. */
  readonly projectId: string | null;
  readonly setAvailable: (available: boolean) => void;
  /** Records which project the current page shows, without touching the panel. */
  readonly setPageProjectId: (projectId: string | null) => void;
  /** No argument: the page's project. `null`: the general panel, whatever page this is. */
  readonly openAssistant: (projectId?: string | null) => void;
  readonly closeAssistant: () => void;
}

const AssistantUIContext = createContext<AssistantUIValue | undefined>(undefined);

const DEFAULT_VALUE: AssistantUIValue = {
  isAvailable: false,
  isOpen: false,
  projectId: null,
  setAvailable: () => {},
  setPageProjectId: () => {},
  openAssistant: () => {},
  closeAssistant: () => {},
};

/**
 * Shared open/closed state for the assistant panel, mounted once in App.tsx
 * (via the AssistantProvider gate, components/assistant/index.tsx) so the
 * header button and the "explain this result" button -- two unrelated,
 * route-remounted points in the tree -- open the same panel instead of two
 * independent ones. Deliberately tiny and free of any assistant-specific
 * copy: it is always bundled, while every string, every network call and the
 * trigger buttons live in this feature's lazy chunks. Callers are the two
 * triggers (triggers.tsx), the panel root, and the page-scope hook in
 * components/assistant/index.tsx; Navbar and ResultsSection only render slots.
 *
 * Two project ids on purpose. `pageProjectId` follows the page (set and
 * cleared by the scope hook as routes change); `projectId` belongs to the
 * panel, is fixed when it opens (the argument, else the page's project) and
 * is replaced only by the next open, so navigating while the panel is open does
 * not quietly change what it is about. Closing keeps it, because the conversation
 * is stored under it and a turn still being answered belongs to that conversation.
 */
export function AssistantUIProvider({ children }: { readonly children: ReactNode }) {
  const [isAvailable, setAvailable] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [pageProjectId, setPageProjectId] = useState<string | null>(null);

  const openAssistant = useCallback(
    (nextProjectId?: string | null) => {
      setProjectId(nextProjectId === undefined ? pageProjectId : nextProjectId);
      setIsOpen(true);
    },
    [pageProjectId]
  );

  const closeAssistant = useCallback(() => {
    setIsOpen(false);
  }, []);

  const value = useMemo(
    () => ({
      isAvailable,
      isOpen,
      projectId,
      setAvailable,
      setPageProjectId,
      openAssistant,
      closeAssistant,
    }),
    [isAvailable, isOpen, projectId, openAssistant, closeAssistant]
  );

  return <AssistantUIContext.Provider value={value}>{children}</AssistantUIContext.Provider>;
}

/**
 * Tolerant on purpose: unlike useAuth(), this never throws without a
 * provider ancestor. Components that render a slot or the scope hook, and
 * the existing tests that render them standalone, must keep working
 * unchanged -- the default simply reports the feature as unavailable, which
 * is also the correct answer for every production build without
 * VITE_ASSISTANT_ENABLED.
 */
export function useAssistantUI(): AssistantUIValue {
  return useContext(AssistantUIContext) ?? DEFAULT_VALUE;
}
