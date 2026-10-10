import { useEffect } from "react";
import { useAuth, registerSignOutListener } from "@/contexts/AuthContext";
import { useAssistantUI } from "@/contexts/AssistantUIContext";
import { useAssistantConfig } from "./useAssistantConfig";
import { AssistantPanel } from "./AssistantPanel";
import { clearAssistantHistory } from "./useAssistantChat";
import "./i18n";

/**
 * The lazy chunk's entry point (see components/assistant/index.tsx for the
 * build-time gate). Everything imported from here -- the panel, its hooks,
 * the locale JSON behind ./i18n -- exists only in this chunk, which a
 * production build without VITE_ASSISTANT_ENABLED never emits.
 */
export default function AssistantRoot() {
  const { isAuthenticated, status, user } = useAuth();
  const { isOpen, projectId, setAvailable, closeAssistant } = useAssistantUI();
  // refreshUser flips the status to "loading" while it re-reads the same session (after the
  // profile is saved, say) and keeps the user. That is not a sign-out, and unmounting the
  // panel for it would abort a running turn; a real sign-out clears the user as well.
  const signedIn = isAuthenticated || (status === "loading" && user !== null);
  const configQuery = useAssistantConfig(signedIn);
  const available = signedIn && configQuery.isSuccess && configQuery.data.enabled;

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

  // One listener for both, so a later user in the same tab never sees these answers.
  useEffect(
    () =>
      registerSignOutListener(() => {
        clearAssistantHistory();
        closeAssistant();
      }),
    [closeAssistant]
  );

  // `available` implies a signed-in user; the check is for the type, which cannot know it.
  if (!available || !user) {
    return null;
  }

  return (
    <AssistantPanel
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) closeAssistant();
      }}
      projectId={projectId}
      userId={user.id}
      mode={configQuery.data.mode}
    />
  );
}
