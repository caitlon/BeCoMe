import { useCallback, useEffect, useRef, useState } from "react";
import i18n, { toSupportedLanguage } from "@/i18n";
import { HttpError, RateLimitError, StreamIncompleteError } from "@/lib/errors";
import { logger } from "@/lib/logger";
import type { AnswerChecks, ChatTurn, SourceRef, TurnTiming } from "@/types/api";
import { streamAssistantMessage } from "./assistant-api";
import { readAssistantSseStream, type AssistantSseEvent } from "./sse";

const MESSAGE_STATUSES = ["pending", "done", "error", "cut", "cancelled"] as const;

export type AssistantMessageStatus = (typeof MESSAGE_STATUSES)[number];

export interface AssistantMessageError {
  readonly code: number;
  readonly detail: string;
  readonly retryAfter?: number;
}

export interface AssistantMessage {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: string;
  readonly status: AssistantMessageStatus;
  readonly sources?: SourceRef[];
  readonly toolsUsed?: string[];
  readonly checks?: AnswerChecks;
  readonly timing?: TurnTiming;
  readonly error?: AssistantMessageError;
  readonly createdAt: number;
}

/** sessionStorage keys are `${STORAGE_PREFIX}:${userId}:${projectId ?? "general"}`. */
export const STORAGE_PREFIX = "assistant-chat";

// AssistantChatRequest.history takes at most 20 entries (api/schemas/assistant.py).
const MAX_HISTORY_ENTRIES = 20;
// The list kept in memory, and the same number is what is stored.
const MAX_MESSAGES = 40;

// Bumped by clearAssistantHistory(). A thread remembers the value it was loaded
// under and stops writing once that value is out of date, so a sign-out cannot be
// undone by a hook that is still mounted when it happens.
let historyEpoch = 0;

interface Thread {
  readonly key: string;
  readonly messages: AssistantMessage[];
  readonly epoch: number;
  // How many times an action (append, settle, clear) asked for the thread to be
  // stored. It travels inside the state with the change it belongs to, so no render
  // can take the request for a save without also holding that change.
  readonly writes: number;
}

function storageKeyFor(userId: string, projectId: string | null): string {
  return `${STORAGE_PREFIX}:${userId}:${projectId ?? "general"}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStoredMessage(value: unknown): value is AssistantMessage {
  if (!isRecord(value)) return false;
  const { error, sources, toolsUsed, checks, timing } = value;
  return (
    typeof value.id === "string" &&
    (value.role === "user" || value.role === "assistant") &&
    typeof value.content === "string" &&
    typeof value.status === "string" &&
    (MESSAGE_STATUSES as readonly string[]).includes(value.status) &&
    typeof value.createdAt === "number" &&
    (error === undefined ||
      (isRecord(error) &&
        typeof error.code === "number" &&
        typeof error.detail === "string" &&
        (error.retryAfter === undefined || typeof error.retryAfter === "number"))) &&
    (sources === undefined || Array.isArray(sources)) &&
    (toolsUsed === undefined || Array.isArray(toolsUsed)) &&
    (checks === undefined || isRecord(checks)) &&
    (timing === undefined || isRecord(timing))
  );
}

// A request cannot outlive the page that made it, so a message stored as pending
// is a partial answer that was cut off, empty or not.
function loadMessages(key: string): AssistantMessage[] {
  try {
    const parsed: unknown = JSON.parse(window.sessionStorage.getItem(key) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(isStoredMessage)
      .slice(-MAX_MESSAGES)
      .map((m) => (m.status === "pending" ? { ...m, status: "cut" } : m));
  } catch {
    return [];
  }
}

// Storage that is blocked, full or absent must never throw out of the hook.
function saveMessages({ key, messages, epoch }: Thread): void {
  if (epoch !== historyEpoch) return;
  try {
    if (messages.length === 0) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, JSON.stringify(messages));
    }
  } catch {
    // The conversation simply is not kept across a reload.
  }
}

/** Removes the conversations of every user and project, for sign-out. */
export function clearAssistantHistory(): void {
  historyEpoch += 1;
  try {
    const storage = window.sessionStorage;
    const keys: string[] = [];
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i);
      if (key?.startsWith(`${STORAGE_PREFIX}:`)) keys.push(key);
    }
    keys.forEach((key) => storage.removeItem(key));
  } catch {
    // Nothing was stored that could be cleared.
  }
}

// Only a message that was sent and answered in full goes back to the server: a
// partial, failed, cut or cancelled answer would teach the model words it never said.
function historyWindow(messages: AssistantMessage[]): number[] {
  const indexes: number[] = [];
  messages.forEach((m, index) => {
    if (m.status === "done") indexes.push(index);
  });
  return indexes.slice(-MAX_HISTORY_ENTRIES);
}

function toError(error: unknown): AssistantMessageError {
  if (error instanceof RateLimitError) {
    return { code: error.status, detail: error.message, retryAfter: error.retryAfter };
  }
  if (error instanceof HttpError) {
    return { code: error.status, detail: error.message };
  }
  return { code: 0, detail: error instanceof Error ? error.message : String(error) };
}

function applyEvent(m: AssistantMessage, event: AssistantSseEvent): AssistantMessage {
  switch (event.type) {
    case "token":
      return { ...m, content: m.content + event.text };
    case "done":
      return {
        ...m,
        content: event.response.answer,
        status: "done",
        sources: event.response.sources,
        toolsUsed: event.response.tools_used,
        checks: event.response.checks,
        timing: event.response.timing,
      };
    case "error":
      return { ...m, status: "error", error: { code: event.code, detail: event.detail } };
  }
}

function applyFailure(
  m: AssistantMessage,
  error: unknown,
  aborted: boolean,
  hasContent: boolean
): AssistantMessage {
  if (aborted) return { ...m, status: "cancelled" };
  // Once an answer has begun, whatever breaks the stream leaves a cut answer:
  // a refusal from the server can only come before the first token.
  if (hasContent) return { ...m, status: "cut" };
  return { ...m, status: "error", error: toError(error) };
}

function patchMessage(
  messages: AssistantMessage[],
  id: string,
  patch: (m: AssistantMessage) => AssistantMessage
): AssistantMessage[] {
  return messages.map((m) => (m.id === id ? patch(m) : m));
}

function markFailed(m: AssistantMessage): AssistantMessage {
  return { ...m, status: "error" };
}

// What the stream has produced so far; the caller reads it after a failure to tell
// a refusal (nothing was said) from a cut answer.
interface StreamProgress {
  finished: boolean;
  hasContent: boolean;
}

async function consumeStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  progress: StreamProgress,
  onEvent: (event: AssistantSseEvent) => void
): Promise<void> {
  for await (const event of readAssistantSseStream(body, signal)) {
    // The reader stops on an abort by itself; this keeps a cancel final even
    // for an event it had already handed over.
    if (signal.aborted) break;
    if (event.type !== "token") progress.finished = true;
    else if (event.text) progress.hasContent = true;
    onEvent(event);
  }
  if (!progress.finished) throw new StreamIncompleteError();
}

// A thread that no longer holds the message (cleared, or another conversation) is
// left as it is.
function patchThread(
  thread: Thread,
  id: string,
  patch: (m: AssistantMessage) => AssistantMessage,
  settles: boolean
): Thread {
  if (!thread.messages.some((m) => m.id === id)) return thread;
  return {
    ...thread,
    messages: patchMessage(thread.messages, id, patch),
    writes: thread.writes + (settles ? 1 : 0),
  };
}

export function useAssistantChat({
  projectId,
  userId,
}: {
  readonly projectId: string | null;
  readonly userId: string;
}) {
  const storageKey = storageKeyFor(userId, projectId);
  const [thread, setThread] = useState<Thread>(() => ({
    key: storageKey,
    messages: loadMessages(storageKey),
    epoch: historyEpoch,
    writes: 0,
  }));
  const [draft, setDraft] = useState("");
  const [now, setNow] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const savedRef = useRef({ key: storageKey, writes: 0 });

  // A different user or project is a different conversation; the render that
  // sees the new key swaps the thread before anything is committed.
  let current = thread;
  if (thread.key !== storageKey) {
    current = { key: storageKey, messages: loadMessages(storageKey), epoch: historyEpoch, writes: 0 };
    setThread(current);
  }
  const { messages } = current;

  const pendingMessage = messages.find((m) => m.status === "pending");
  const isPending = pendingMessage !== undefined;
  const startedAt = pendingMessage?.createdAt ?? null;
  const pendingSeconds = startedAt === null ? 0 : Math.max(0, Math.floor((now - startedAt) / 1000));

  // Stored after a turn is appended (the answer still empty), settles or is cleared,
  // never on mount and never while tokens are arriving: a stream of any length
  // writes storage twice.
  useEffect(() => {
    const saved = savedRef.current;
    savedRef.current = { key: current.key, writes: current.writes };
    if (saved.key !== current.key || saved.writes === current.writes) return;
    saveMessages(current);
  }, [current]);

  useEffect(() => {
    if (!isPending) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [isPending]);

  // The Sheet keeps the panel mounted while it is open, so closing it does not
  // cancel; the root going away, or the conversation changing under a request,
  // does. The partial answer is dropped with it and is not written to storage.
  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [storageKey]
  );

  const sendMessage = useCallback(async () => {
    const text = draft.trim();
    if (!text || abortRef.current) return;

    const startedAtMs = Date.now();
    const pendingId = crypto.randomUUID();
    const history: ChatTurn[] = historyWindow(current.messages).map((index) => ({
      role: current.messages[index].role,
      content: current.messages[index].content,
    }));
    const userMessage: AssistantMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      status: "done",
      createdAt: startedAtMs,
    };
    const answer: AssistantMessage = {
      id: pendingId,
      role: "assistant",
      content: "",
      status: "pending",
      createdAt: startedAtMs,
    };

    const patchAnswer = (patch: (m: AssistantMessage) => AssistantMessage, settles = false) =>
      setThread((prev) => patchThread(prev, pendingId, patch, settles));
    // The turn ends here, so what it leaves behind is worth storing.
    const settleAnswer = (patch: (m: AssistantMessage) => AssistantMessage) =>
      patchAnswer(patch, true);

    // Nothing was answered, so the question goes back into the box, unless the
    // user has already started typing another one. The question is marked as
    // failed too, so the next request does not carry it a second time.
    const restoreDraft = () => {
      setDraft((d) => d || text);
      setThread((prev) => ({
        ...prev,
        messages: patchMessage(prev.messages, userMessage.id, markFailed),
        writes: prev.writes + 1,
      }));
    };
    const progress: StreamProgress = { finished: false, hasContent: false };

    const controller = new AbortController();
    abortRef.current = controller;
    setThread({
      ...current,
      messages: [...current.messages, userMessage, answer].slice(-MAX_MESSAGES),
      writes: current.writes + 1,
    });
    setDraft("");
    setNow(startedAtMs);

    try {
      const response = await streamAssistantMessage(
        { message: text, history, project_id: projectId, locale: toSupportedLanguage(i18n.language) },
        controller.signal
      );
      if (!response.body) throw new StreamIncompleteError();

      await consumeStream(response.body, controller.signal, progress, (event) => {
        patchAnswer((m) => applyEvent(m, event), event.type !== "token");
        if (event.type === "error" && !progress.hasContent) restoreDraft();
      });
    } catch (error) {
      const aborted = controller.signal.aborted;
      // The class only: a message can carry a host or a piece of the user's text.
      if (!aborted) {
        logger.error("Assistant turn failed", { error: error instanceof Error ? error.name : typeof error });
      }
      settleAnswer((m) => applyFailure(m, error, aborted, progress.hasContent));
      if (!aborted && !progress.hasContent) restoreDraft();
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [draft, current, projectId]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setThread((prev) => ({ ...prev, messages: [], writes: prev.writes + 1 }));
  }, []);

  const sentIndexes = historyWindow(messages);
  const historyWindowStart = sentIndexes.length > 0 ? sentIndexes[0] : -1;

  return {
    messages,
    draft,
    setDraft,
    sendMessage,
    cancel,
    clear,
    isPending,
    pendingSeconds,
    startedAt,
    historyWindowStart,
  };
}
