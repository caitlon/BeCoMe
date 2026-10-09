import { useEffect } from "react";
import { useAuth, registerSignOutListener } from "@/contexts/AuthContext";
import { useAssistantUI } from "@/contexts/AssistantUIContext";
import { useAssistantConfig } from "./useAssistantConfig";
import { AssistantPanel } from "./AssistantPanel";
import "./i18n";

/**
 * The lazy chunk's entry point (see components/assistant/index.tsx for the
 * build-time gate). Everything imported from here -- the panel, its hooks,
 * the locale JSON behind ./i18n -- exists only in this chunk, which a
 * production build without VITE_ASSISTANT_ENABLED never emits.
 */
export default function AssistantRoot() {
  const { isAuthenticated } = useAuth();
  const { isOpen, projectId, setAvailable, closeAssistant } = useAssistantUI();
  const configQuery = useAssistantConfig(isAuthenticated);
  const available = isAuthenticated && configQuery.isSuccess && configQuery.data.enabled;

  useEffect(() => {
    setAvailable(available);
  }, [available, setAvailable]);

  // If this root goes away (for example its error boundary swallowed a throw),
  // the context must not keep reporting the feature available with no panel.
  useEffect(
    () => () => {
      setAvailable(false);
      closeAssistant();
    },
    [setAvailable, closeAssistant]
  );

  useEffect(() => registerSignOutListener(closeAssistant), [closeAssistant]);

  if (!available) {
    return null;
  }

  return (
    <AssistantPanel
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) closeAssistant();
      }}
      projectId={projectId}
    />
  );
}
