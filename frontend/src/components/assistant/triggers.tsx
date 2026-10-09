import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAssistantUI } from "@/contexts/AssistantUIContext";
import "./i18n";

/**
 * The header button. Lives in this lazy chunk (loaded only through
 * components/assistant/index.tsx's AssistantHeaderSlot) rather than in
 * Navbar.tsx itself, so that Navbar -- always bundled -- never references an
 * assistant.json key or the "assistant" i18n namespace at all. It opens the
 * panel for the project the current page registered, if any.
 */
export function HeaderTrigger() {
  const { t } = useTranslation("assistant");
  const { isAvailable, projectId, openAssistant } = useAssistantUI();

  if (!isAvailable) return null;

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => openAssistant(projectId ?? undefined)}
      aria-label={t("trigger.header")}
      title={t("trigger.header")}
      className="w-10 h-10 hover:bg-muted transition-colors duration-300"
    >
      <Sparkles className="h-4 w-4" />
    </Button>
  );
}

export interface ResultTriggerProps {
  readonly projectId: string;
}

/** The "explain this result" button. Same reasoning as HeaderTrigger. */
export function ResultTrigger({ projectId }: ResultTriggerProps) {
  const { t } = useTranslation("assistant");
  const { isAvailable, openAssistant } = useAssistantUI();

  if (!isAvailable) return null;

  return (
    <div className="mt-3 flex justify-center">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => openAssistant(projectId)}
        className="gap-2 text-muted-foreground"
      >
        <Sparkles className="h-4 w-4" />
        {t("trigger.result")}
      </Button>
    </div>
  );
}
