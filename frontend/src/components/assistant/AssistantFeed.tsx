import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";
import { useAssistantUI } from "@/contexts/AssistantUIContext";
import type { AssistantConfigResponse } from "@/types/api";
import { AssistantMessage, type NotFoundActions } from "./AssistantMessage";
import { AssistantPending, AssistantPendingStatus } from "./AssistantPending";
import type { AssistantMessage as AssistantMessageData } from "./useAssistantChat";

// How far from the bottom the user may be and still count as following the answer.
const BOTTOM_TOLERANCE_PX = 48;

function newestUserId(messages: readonly AssistantMessageData[]): string | undefined {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user") return messages[i].id;
  }
  return undefined;
}

/**
 * Keeps the newest content in view while the user is at the bottom, and leaves the
 * scroll alone once they have gone up to read. A new question always brings the
 * bottom back, since it is the user's own act. Returns the scroll handler to attach.
 */
function useStickToBottom(ref: RefObject<HTMLDivElement | null>, messages: readonly AssistantMessageData[]) {
  const atBottom = useRef(true);
  const seenUserId = useRef<string | undefined>(undefined);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const userId = newestUserId(messages);
    const asked = userId !== seenUserId.current;
    seenUserId.current = userId;
    if (asked || atBottom.current) element.scrollTop = element.scrollHeight;
  }, [ref, messages]);

  return useCallback(() => {
    const element = ref.current;
    if (!element) return;
    atBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight <= BOTTOM_TOLERANCE_PX;
  }, [ref]);
}

/**
 * True once a 429 has waited out its Retry-After, counted from the turn that was
 * refused. True at once for anything else, so only a refusal with a wait holds back.
 */
function useRetryAfterElapsed(message: AssistantMessageData | undefined): boolean {
  const seconds = message?.error?.code === 429 ? message.error.retryAfter : undefined;
  const readyAt = message && seconds !== undefined && Number.isFinite(seconds) ? message.createdAt + seconds * 1000 : 0;
  // A wait that is over already when the block first renders must not show the retry a tick late.
  const [elapsedFor, setElapsedFor] = useState(() => (readyAt !== 0 && readyAt <= Date.now() ? readyAt : 0));

  useEffect(() => {
    if (readyAt === 0) return;
    const timer = setTimeout(() => setElapsedFor(readyAt), Math.max(0, readyAt - Date.now()));
    return () => clearTimeout(timer);
  }, [readyAt]);

  return readyAt === 0 || elapsedFor === readyAt;
}

function HistorySeparator() {
  const { t } = useTranslation("assistant");

  return (
    <div role="separator" className="flex items-center gap-2 text-[11px] text-muted-foreground">
      <span className="h-px flex-1 bg-border" />
      <span>{t("feed.older")}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

export interface AssistantFeedProps {
  readonly messages: AssistantMessageData[];
  /** Index of the oldest message the next request still carries; -1 when none. */
  readonly historyWindowStart: number;
  readonly isPending: boolean;
  readonly pendingSeconds: number;
  readonly mode: AssistantConfigResponse["mode"];
  /** Sends the given question again as a new turn. */
  readonly onRetry: (text: string) => void;
  /** The conversation is about a project, not the general thread. */
  readonly projectScoped?: boolean;
}

/**
 * The conversation. A log that is marked busy while a turn runs, so a screen reader
 * does not read out every token; the failure block of a turn that has just broken is
 * the one thing announced, by its own alert role.
 */
export function AssistantFeed({
  messages,
  historyWindowStart,
  isPending,
  pendingSeconds,
  mode,
  onRetry,
  projectScoped = false,
}: AssistantFeedProps) {
  const { t } = useTranslation("assistant");
  const { openAssistant, closeAssistant } = useAssistantUI();
  const scrollRef = useRef<HTMLDivElement>(null);
  const handleScroll = useStickToBottom(scrollRef, messages);
  const last = messages[messages.length - 1];
  // A failure that was already on screen when the feed opened is history, not news.
  // An answer still pending then is not: the feed opens with the first question.
  const [openedWithId] = useState(() => (last?.status === "pending" ? undefined : last?.id));
  const previous = messages[messages.length - 2];
  const failed = !isPending && last?.role === "assistant" && (last.status === "error" || last.status === "cut");
  const projectGone = failed && last.error?.code === 404;
  const retryWaited = useRetryAfterElapsed(failed ? last : undefined);

  // Only the last answer can be tried again, and only with its own question. These
  // are memoised, and handed to nothing else, so no settled message ever sees a new one.
  const question = previous?.role === "user" ? previous.content : undefined;
  const retryable = failed && !projectGone && retryWaited && question !== undefined;
  const handleRetry = useMemo(
    () => (retryable ? () => onRetry(question) : undefined),
    [retryable, onRetry, question],
  );
  const notFound = useMemo<NotFoundActions | undefined>(
    () =>
      projectGone
        ? { onAskWithout: projectScoped ? () => openAssistant(null) : undefined, onOpenProjects: closeAssistant }
        : undefined,
    [projectGone, projectScoped, openAssistant, closeAssistant],
  );

  // The divider says where the next request's memory begins, so there is nothing to
  // say when no answered message lies before that point.
  const separatorAt =
    historyWindowStart > 0 && messages.slice(0, historyWindowStart).some((m) => m.status === "done")
      ? historyWindowStart
      : -1;

  return (
    <>
      <div
        ref={scrollRef}
        role="log"
        aria-label={t("feed.label")}
        aria-busy={isPending}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto break-words px-4 py-4"
      >
        <div className="flex flex-col gap-3">
          {messages.map((message, index) => {
            const isLast = message === last;
            const unanswered = message.status === "pending" && message.content.trim() === "";
            return (
              <Fragment key={message.id}>
                {index === separatorAt && <HistorySeparator />}
                {unanswered ? (
                  <AssistantPending mode={mode} seconds={pendingSeconds} hasProject={projectScoped} />
                ) : (
                  <AssistantMessage
                    message={message}
                    onRetry={isLast ? handleRetry : undefined}
                    notFound={isLast ? notFound : undefined}
                    announce={isLast && message.id !== openedWithId}
                  />
                )}
              </Fragment>
            );
          })}
        </div>
      </div>
      <AssistantPendingStatus active={isPending} mode={mode} seconds={pendingSeconds} hasProject={projectScoped} />
    </>
  );
}
