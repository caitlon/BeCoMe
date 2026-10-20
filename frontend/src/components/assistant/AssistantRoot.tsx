import { useCallback, useEffect, useState } from "react";
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
  const { isOpen, projectId, setAvailable, closeAssistant, forgetProject } = useAssistantUI();
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

  // One reset for sign-out and for a switch between two users, so a later user in the same tab
  // never sees these answers.
  const resetForUser = useCallback(() => {
    clearAssistantHistory();
    closeAssistant();
    forgetProject();
  }, [closeAssistant, forgetProject]);

  useEffect(() => registerSignOutListener(resetForUser), [resetForUser]);

  // The sign-out listener does not fire when another tab swaps the session and this tab re-reads
  // it (refreshUser), so a change from one user id to another resets here. The panel is rendered
  // only for the user this effect has caught up with: the reset and the new user's panel then land
  // in one render, so that panel starts closed, without the old project, under the bumped history
  // epoch. The first sign-in and a re-read of the same user reset nothing. A sign-out in between
  // (A, then nobody, then B) sets this back to null, because the sign-out listener has already
  // reset everything and B must not wipe what it stored since.
  const [panelUserId, setPanelUserId] = useState<string | null>(null);
  const userId = user?.id ?? null;
  useEffect(() => {
    if (panelUserId !== null && userId !== null && panelUserId !== userId) {
      resetForUser();
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- must land with resetForUser's updates
    setPanelUserId(userId);
  }, [userId, panelUserId, resetForUser]);

  // `available` implies a signed-in user; the check is for the type, which cannot know it.
  if (!available || !user || panelUserId !== user.id) {
    return null;
  }

  return (
    <AssistantPanel
      key={user.id}
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
