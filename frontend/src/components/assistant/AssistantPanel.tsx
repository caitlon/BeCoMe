import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Sparkles, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { useMediaQuery } from "@/hooks/use-media-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { cn } from "@/lib/utils";
import type { AssistantConfigResponse, ProjectWithRole } from "@/types/api";
import { AssistantComposer } from "./AssistantComposer";
import { AssistantFeed } from "./AssistantFeed";
import { useAssistantChat } from "./useAssistantChat";

const SUGGESTION_INDEXES = [0, 1, 2] as const;

function ProjectScopeLabel({ projectId }: { readonly projectId: string }) {
  const { t } = useTranslation("assistant");
  // Reads the project page's cached entry (same key) and never fetches on its
  // own, so opening the panel adds no request; without the entry the label is
  // generic. The real queryFn matters: the options of the last observer are
  // what a refetch of the shared key runs, so a placeholder here would break
  // the project page's own invalidation while the panel is open.
  const projectQuery = useQuery<ProjectWithRole>({
    queryKey: queryKeys.project(projectId),
    queryFn: () => api.getProject(projectId),
    enabled: false,
  });

  return projectQuery.data?.name
    ? t("panel.scopeProject", { name: projectQuery.data.name })
    : t("panel.scopeGeneral");
}

interface ClearConfirmProps {
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
}

/** The strip under the header that asks before the conversation is wiped. */
function ClearConfirm({ onConfirm, onCancel }: ClearConfirmProps) {
  const { t } = useTranslation("assistant");
  const keepRef = useRef<HTMLButtonElement>(null);
  const question = t("panel.clearConfirm");

  // The safe answer takes the focus, so an Enter pressed in passing does not wipe anything.
  useEffect(() => {
    keepRef.current?.focus();
  }, []);

  return (
    <div role="group" aria-label={question} className="flex items-center gap-2 border-b bg-muted/50 px-4 py-2 text-[13px]">
      <span className="flex-1">{question}</span>
      <Button type="button" variant="outline" size="sm" className="border-destructive" onClick={onConfirm}>
        {t("panel.clearYes")}
      </Button>
      <Button ref={keepRef} type="button" variant="ghost" size="sm" onClick={onCancel}>
        {t("panel.clearNo")}
      </Button>
    </div>
  );
}

interface EmptyStateProps {
  readonly scoped: boolean;
  readonly onSuggestion: (text: string) => void;
}

function EmptyState({ scoped, onSuggestion }: EmptyStateProps) {
  const { t } = useTranslation("assistant");
  const suggestionsKey = scoped ? "empty.suggestionsProject" : "empty.suggestionsGeneral";

  return (
    <div className="flex-1 overflow-y-auto px-5 py-7 text-center">
      <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-muted">
        <Sparkles className="h-5 w-5" aria-hidden="true" />
      </div>
      <h3 className="mb-1.5 font-display text-lg font-medium">
        {scoped ? t("empty.titleProject") : t("empty.titleGeneral")}
      </h3>
      <p className="mb-4 text-sm text-muted-foreground">
        {t("empty.hint")}
        <br />
        <span className="text-xs">{t("panel.seesOnly")}</span>
      </p>
      <div className="flex flex-col gap-1.5">
        {SUGGESTION_INDEXES.map((index) => {
          const text = t(`${suggestionsKey}.${index}`);
          return (
            <Button
              key={index}
              variant="outline"
              className="h-auto justify-start whitespace-normal bg-card px-3 py-2 text-left font-normal"
              onClick={() => onSuggestion(text)}
            >
              {text}
            </Button>
          );
        })}
      </div>
    </div>
  );
}

export interface AssistantPanelProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly projectId: string | null;
  readonly userId: string;
  /** How the backend answers, which decides what a pending answer looks like. */
  readonly mode: AssistantConfigResponse["mode"];
}

/**
 * The panel: header, conversation, composer and footer. A right-hand sheet that
 * leaves the page interactive on desktop, a modal bottom sheet below the md
 * breakpoint. Owns the conversation, so it outlives a closed sheet.
 */
export function AssistantPanel({ open, onOpenChange, projectId, userId, mode }: AssistantPanelProps) {
  const { t } = useTranslation("assistant");
  const { t: tCommon } = useTranslation("common");
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const chat = useAssistantChat({ projectId, userId });
  const { messages, isPending } = chat;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const clearButtonRef = useRef<HTMLButtonElement>(null);
  // The confirmation belongs to one conversation: another one, or none, does not inherit it.
  const conversationKey = `${userId}:${projectId ?? "general"}`;
  const [confirmingFor, setConfirmingFor] = useState<string | null>(null);
  const confirming = confirmingFor === conversationKey;

  const scoped = Boolean(projectId);
  const canClear = messages.length > 0 && !isPending;
  // One that has since started a turn, been emptied, or lost its sheet to a close is stale too.
  if (confirmingFor !== null && (!open || !canClear)) setConfirmingFor(null);

  function handleSuggestion(text: string) {
    chat.setDraft(text);
    textareaRef.current?.focus();
  }

  function handleCancelClear() {
    setConfirmingFor(null);
    clearButtonRef.current?.focus();
  }

  function handleConfirmClear() {
    chat.clear();
    setConfirmingFor(null);
    textareaRef.current?.focus();
  }

  // Esc backs out of the confirmation first, and never closes the sheet while a turn is
  // running: Stop is the only way to cancel one.
  function handleEscape(event: KeyboardEvent) {
    if (isPending) {
      event.preventDefault();
    } else if (confirming) {
      event.preventDefault();
      handleCancelClear();
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange} modal={!isDesktop}>
      <SheetContent
        side={isDesktop ? "right" : "bottom"}
        showCloseButton={false}
        onInteractOutside={(event) => event.preventDefault()}
        onEscapeKeyDown={handleEscape}
        onOpenAutoFocus={(event) => {
          // The question box, not the first button of the header: the panel is opened to ask.
          event.preventDefault();
          textareaRef.current?.focus();
        }}
        className={cn(
          "flex flex-col gap-0 p-0",
          isDesktop ? "w-full sm:max-w-[440px]" : "h-[94dvh] rounded-t-2xl",
        )}
      >
        <header className="flex items-center gap-2.5 border-b px-4 pb-2.5 pt-3.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <SheetTitle className="font-display text-lg font-medium leading-tight">
              {t("panel.title")}
            </SheetTitle>
            <SheetDescription className="truncate text-xs">
              {projectId ? <ProjectScopeLabel projectId={projectId} /> : t("panel.scopeGeneral")}
            </SheetDescription>
          </div>
          <Button
            ref={clearButtonRef}
            variant="ghost"
            size="icon"
            disabled={!canClear}
            onClick={() => setConfirmingFor(conversationKey)}
            aria-label={t("panel.clear")}
            title={t("panel.clear")}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <SheetClose asChild>
            <Button variant="ghost" size="icon" aria-label={tCommon("a11y.close")} title={tCommon("a11y.close")}>
              <X className="h-4 w-4" />
            </Button>
          </SheetClose>
        </header>

        {confirming && <ClearConfirm onConfirm={handleConfirmClear} onCancel={handleCancelClear} />}

        {messages.length === 0 ? (
          <EmptyState scoped={scoped} onSuggestion={handleSuggestion} />
        ) : (
          <AssistantFeed
            key={conversationKey}
            messages={messages}
            historyWindowStart={chat.historyWindowStart}
            isPending={isPending}
            pendingSeconds={chat.pendingSeconds}
            mode={mode}
            onRetry={chat.retry}
            projectScoped={scoped}
          />
        )}

        <AssistantComposer
          value={chat.draft}
          onChange={chat.setDraft}
          onSend={chat.sendMessage}
          onCancel={chat.cancel}
          isPending={isPending}
          textareaRef={textareaRef}
        />

        <p className="px-4 pb-2.5 text-center text-[11px] text-muted-foreground">{t("panel.footer")}</p>
      </SheetContent>
    </Sheet>
  );
}
