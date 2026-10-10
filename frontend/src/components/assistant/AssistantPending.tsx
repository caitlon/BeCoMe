import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import type { AssistantConfigResponse } from "@/types/api";

// Where the second and the third phase of an answer that does not stream begin.
const READING_FROM_SECONDS = 3;
const WRITING_FROM_SECONDS = 8;

export interface AssistantPendingProps {
  readonly mode: AssistantConfigResponse["mode"];
  readonly seconds: number;
  /** Some of the answer is already on screen. */
  readonly hasText: boolean;
}

function phaseKey(seconds: number): "searching" | "reading" | "writing" {
  if (seconds < READING_FROM_SECONDS) return "searching";
  if (seconds < WRITING_FROM_SECONDS) return "reading";
  return "writing";
}

/**
 * What stands in for an answer that has not arrived. The workflow mode streams, so
 * the text itself is the progress and a cursor follows it; hybrid and agent send the
 * whole answer at once, after minutes of work the user cannot see, so the phase is
 * guessed from the time that has passed.
 */
export function AssistantPending({ mode, seconds, hasText }: AssistantPendingProps) {
  const { t } = useTranslation("assistant");

  if (mode === "workflow" && hasText) {
    return (
      <span
        aria-hidden="true"
        className="inline-block h-4 w-0.5 animate-pulse bg-foreground align-middle motion-reduce:animate-none"
      />
    );
  }

  const label = mode === "workflow" ? t("message.pending.answering") : t(`message.pending.${phaseKey(seconds)}`);

  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden="true" />
      <span>{label}</span>
    </p>
  );
}
