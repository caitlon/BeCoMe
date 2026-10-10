import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import type { AssistantConfigResponse } from "@/types/api";

// Where the second and the third phase of an answer that does not stream begin.
const READING_FROM_SECONDS = 3;
const WRITING_FROM_SECONDS = 8;

type PendingMode = AssistantConfigResponse["mode"];
type PendingLabel = "searching" | "reading" | "writing" | "answering";

export interface AssistantPendingProps {
  readonly mode: PendingMode;
  readonly seconds: number;
  /** Whether the conversation is about a project, which decides if there is one to read. */
  readonly hasProject: boolean;
}

function pendingLabel(mode: PendingMode, seconds: number, hasProject: boolean): PendingLabel {
  if (mode === "workflow") return "answering";
  if (seconds >= WRITING_FROM_SECONDS) return "writing";
  // Without a project there is nothing to read between the search and the writing.
  if (seconds >= READING_FROM_SECONDS && hasProject) return "reading";
  return "searching";
}

/**
 * What stands in for an answer that has not started to arrive. The workflow mode
 * streams, so once text comes the text is the progress and this goes away; hybrid and
 * agent send the whole answer at once, after minutes of work the user cannot see, so
 * the phase is guessed from the time that has passed.
 */
export function AssistantPending({ mode, seconds, hasProject }: AssistantPendingProps) {
  const { t } = useTranslation("assistant");

  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden="true" />
      <span>{t(`message.pending.${pendingLabel(mode, seconds, hasProject)}`)}</span>
    </p>
  );
}

export interface AssistantPendingStatusProps extends AssistantPendingProps {
  readonly active: boolean;
}

/**
 * The same phase for a screen reader. The conversation is marked busy while a turn
 * runs, so the visible indicator inside it is not read out; this one lives outside it
 * and its text changes only when the phase does, which is when it is announced. The
 * closing ellipsis is left off: some screen readers say it aloud.
 */
export function AssistantPendingStatus({ active, mode, seconds, hasProject }: AssistantPendingStatusProps) {
  const { t } = useTranslation("assistant");

  return (
    <p role="status" className="sr-only">
      {active ? t(`message.pending.${pendingLabel(mode, seconds, hasProject)}`).replace(/…$/, "") : ""}
    </p>
  );
}
