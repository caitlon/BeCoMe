import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Info, OctagonX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AnswerChecks } from "@/types/api";
import { AssistantMarkdown } from "./AssistantMarkdown";
import { AssistantSources } from "./AssistantSources";
import { cleanChecks, cleanSources, cleanToolsUsed, sourceAnchorId } from "./message-shape";
import type { AssistantMessage as AssistantMessageData, AssistantMessageError } from "./useAssistantChat";

const KNOWN_TOOLS = [
  "search_docs",
  "list_my_projects",
  "get_project",
  "get_project_result",
  "get_project_opinions",
];

interface FailureBlockProps {
  readonly cut: boolean;
  readonly error?: AssistantMessageError;
  readonly onRetry?: () => void;
}

/**
 * The red block of a failed or interrupted turn. The text is chosen by the status code
 * from fixed copy: `error.detail` is whatever the server or the network said, and is
 * never shown.
 */
function FailureBlock({ cut, error, onRetry }: FailureBlockProps) {
  const { t } = useTranslation("assistant");
  let title = t("message.errors.generic");
  let hint: string | null = null;

  if (cut) {
    title = t("message.errors.cut");
    hint = t("message.errors.cutHint");
  } else if (error?.code === 429) {
    const seconds = error.retryAfter;
    title =
      seconds !== undefined && Number.isFinite(seconds) && seconds > 0
        ? t("message.errors.rateLimited", { minutes: Math.ceil(seconds / 60) })
        : t("message.errors.rateLimitedGeneric");
  } else if (error?.code === 503) {
    title = t("message.errors.unavailable");
    hint = t("message.errors.unavailableHint");
  } else if (error?.code === 404) {
    title = t("message.errors.notFound");
    hint = t("message.errors.notFoundHint");
  }

  return (
    <div className="mt-2 flex items-start gap-2.5 rounded-lg border border-destructive/50 bg-destructive/5 px-3 py-2.5 text-[13px]">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
      <div>
        <p className="font-medium">{title}</p>
        {hint && <p className="mt-0.5 text-[12.5px] text-muted-foreground">{hint}</p>}
        {onRetry && (
          <Button type="button" variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            {t("message.retry")}
          </Button>
        )}
      </div>
    </div>
  );
}

function ChecksLines({ checks }: { readonly checks: AnswerChecks }) {
  const { t } = useTranslation("assistant");
  const lines: string[] = [];
  if (!checks.numbers_grounded) {
    lines.push(t("message.numbersNotConfirmed", { numbers: checks.ungrounded_numbers.join(", ") }));
  }
  if (!checks.citations_valid) {
    lines.push(t("message.citationInvalid"));
  }

  return lines.map((line) => (
    <p key={line} className="mt-2 flex items-start gap-2 text-[12.5px] text-warning">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{line}</span>
    </p>
  ));
}

function ToolsLine({ tools }: { readonly tools: readonly string[] }) {
  const { t } = useTranslation("assistant");
  const labels = tools.map((tool) => (KNOWN_TOOLS.includes(tool) ? t(`message.tools.${tool}`) : tool));

  return (
    <p className="mt-2 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
      <Info className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span>{t("message.read", { tools: labels.join(", ") })}</span>
    </p>
  );
}

export interface AssistantMessageProps {
  readonly message: AssistantMessageData;
  readonly onRetry?: () => void;
}

function AssistantAnswer({ message, onRetry }: AssistantMessageProps) {
  const { t } = useTranslation("assistant");
  const [openN, setOpenN] = useState<number | null>(null);
  const sources = useMemo(() => cleanSources(message.sources), [message.sources]);
  const sourceNumbers = useMemo(() => sources.map((source) => source.n), [sources]);
  const tools = cleanToolsUsed(message.toolsUsed);
  const checks = cleanChecks(message.checks);

  const { status } = message;
  const partial = status === "error" || status === "cut" || status === "cancelled";

  function handleCite(n: number) {
    setOpenN(n);
    document.getElementById(sourceAnchorId(message.id, n))?.scrollIntoView?.({ block: "nearest" });
  }

  function handleToggle(n: number) {
    setOpenN((current) => (current === n ? null : n));
  }

  return (
    <div className="text-sm">
      {message.content.trim() !== "" && (
        <div
          className={cn(
            "[&_li]:my-0.5 [&_ol]:mb-2 [&_ol]:list-decimal [&_ol]:pl-[18px] [&_p]:mb-2 [&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-[18px]",
            partial && "border-l-2 border-dashed pl-2.5 opacity-75",
          )}
        >
          <AssistantMarkdown
            content={message.content}
            messageId={message.id}
            sourceNumbers={sourceNumbers}
            onCite={handleCite}
          />
        </div>
      )}
      {status === "cancelled" && (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          <OctagonX className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span>{t("message.stopped")}</span>
          <span>· {t("message.stoppedHint")}</span>
        </p>
      )}
      {(status === "error" || status === "cut") && (
        <FailureBlock cut={status === "cut"} error={message.error} onRetry={onRetry} />
      )}
      {checks && <ChecksLines checks={checks} />}
      {sources.length > 0 && (
        <AssistantSources messageId={message.id} sources={sources} openN={openN} onToggle={handleToggle} />
      )}
      {tools.length > 0 && <ToolsLine tools={tools} />}
    </div>
  );
}

/** One turn of the conversation. The user's text is never read as markdown. */
export function AssistantMessage({ message, onRetry }: AssistantMessageProps) {
  if (message.role === "user") {
    return (
      <div className="ml-auto max-w-[80%] whitespace-pre-wrap rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
        {message.content}
      </div>
    );
  }
  return <AssistantAnswer message={message} onRetry={onRetry} />;
}
