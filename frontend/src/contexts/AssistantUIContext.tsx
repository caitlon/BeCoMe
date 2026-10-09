import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface AssistantUIValue {
  readonly isAvailable: boolean;
  readonly isOpen: boolean;
  readonly projectId: string | null;
  readonly setAvailable: (available: boolean) => void;
  readonly openAssistant: (projectId?: string) => void;
  readonly closeAssistant: () => void;
}

const AssistantUIContext = createContext<AssistantUIValue | undefined>(undefined);

const DEFAULT_VALUE: AssistantUIValue = {
  isAvailable: false,
  isOpen: false,
  projectId: null,
  setAvailable: () => {},
  openAssistant: () => {},
  closeAssistant: () => {},
};

/**
 * Shared open/closed state for the assistant panel (BCM-120/BCM-128), mounted
 * once in App.tsx (via the AssistantProvider gate, components/assistant/index.tsx)
 * so the header button and the "ask about this result" button -- two
 * unrelated, route-remounted points in the tree -- open the same
 * conversation instead of two independent ones. Deliberately tiny and free
 * of any assistant-specific copy: it is always bundled, while every string,
 * every network call, and the header/result trigger buttons themselves
 * (components/assistant/triggers.tsx, the only direct callers of
 * useAssistantUI below) live in this feature's two lazy chunks.
 */
export function AssistantUIProvider({ children }: { readonly children: ReactNode }) {
  const [isAvailable, setAvailable] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);

  const openAssistant = useCallback((nextProjectId?: string) => {
    setProjectId(nextProjectId ?? null);
    setIsOpen(true);
  }, []);

  const closeAssistant = useCallback(() => setIsOpen(false), []);

  const value = useMemo(
    () => ({ isAvailable, isOpen, projectId, setAvailable, openAssistant, closeAssistant }),
    [isAvailable, isOpen, projectId, openAssistant, closeAssistant]
  );

  return <AssistantUIContext.Provider value={value}>{children}</AssistantUIContext.Provider>;
}

/**
 * Tolerant on purpose: unlike useAuth(), this never throws without a
 * provider ancestor. Navbar and ResultsSection call it unconditionally, and
 * the existing tests that render them standalone must keep passing
 * unchanged -- the default simply reports the feature as unavailable, which
 * is also the correct answer for every production build without
 * VITE_ASSISTANT_ENABLED.
 */
export function useAssistantUI(): AssistantUIValue {
  return useContext(AssistantUIContext) ?? DEFAULT_VALUE;
}
