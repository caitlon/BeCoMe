import { useCallback, useEffect, useRef, useState } from "react";
import i18n, { toSupportedLanguage } from "@/i18n";
import { HttpError, RateLimitError, StreamIncompleteError } from "@/lib/errors";
import { logger } from "@/lib/logger";
import type { AnswerChecks, ChatTurn, SourceRef, TurnTiming } from "@/types/api";
import { streamAssistantMessage } from "./assistant-api";
import { readAssistantSseStream, type AssistantSseEvent } from "./sse";

export type AssistantMessageStatus = "pending" | "done" | "error" | "cut" | "cancelled";

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

// AssistantChatRequest.history takes at most 20 entries (api/schemas/assistant.py).
const MAX_HISTORY_ENTRIES = 20;
// The most messages kept in a conversation.
const MAX_MESSAGES = 40;

interface Thread {
  readonly key: string;
  readonly messages: AssistantMessage[];
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

/**
 * `userId` is the signed-in user the conversation belongs to. The hook does not read
 * it: a conversation lives in memory and is told apart by project alone.
 */
export function useAssistantChat({
  projectId,
}: {
  readonly projectId: string | null;
  readonly userId: string;
}) {
  const threadKey = projectId ?? "general";
  const [thread, setThread] = useState<Thread>(() => ({ key: threadKey, messages: [] }));
  const [draft, setDraft] = useState("");
  const [now, setNow] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  // A different project is a different conversation; the render that sees the
  // new key swaps the thread before anything is committed.
  let current = thread;
  if (thread.key !== threadKey) {
    current = { key: threadKey, messages: [] };
    setThread(current);
  }
  const { messages } = current;

  const pendingMessage = messages.find((m) => m.status === "pending");
  const isPending = pendingMessage !== undefined;
  const startedAt = pendingMessage?.createdAt ?? null;
  const pendingSeconds = startedAt === null ? 0 : Math.max(0, Math.floor((now - startedAt) / 1000));

  useEffect(() => {
    if (!isPending) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [isPending]);

  // The Sheet keeps the panel mounted while it is open, so closing it does not
  // cancel; the root going away, or the conversation changing under a request, does.
  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [threadKey]
  );

  const sendMessage = useCallback(async () => {
    const text = draft.trim();
    if (!text || abortRef.current) return;

    const key = current.key;
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

    const patchAnswer = (patch: (m: AssistantMessage) => AssistantMessage) =>
      setThread((prev) => ({
        ...prev,
        messages: prev.messages.map((m) => (m.id === pendingId ? patch(m) : m)),
      }));

    // Nothing was answered, so the question goes back into the box, unless the
    // user has already started typing another one. The question is marked as
    // failed too, so the next request does not carry it a second time.
    const restoreDraft = () => {
      setDraft((d) => d || text);
      setThread((prev) => ({
        ...prev,
        messages: prev.messages.map((m) =>
          m.id === userMessage.id ? { ...m, status: "error" } : m
        ),
      }));
    };
    let hasContent = false;

    const controller = new AbortController();
    abortRef.current = controller;
    setThread({ key, messages: [...current.messages, userMessage, answer].slice(-MAX_MESSAGES) });
    setDraft("");
    setNow(startedAtMs);

    try {
      const response = await streamAssistantMessage(
        { message: text, history, project_id: projectId, locale: toSupportedLanguage(i18n.language) },
        controller.signal
      );
      if (!response.body) throw new StreamIncompleteError();

      let finished = false;
      for await (const event of readAssistantSseStream(response.body, controller.signal)) {
        // The reader stops on an abort by itself; this keeps a cancel final even
        // for an event it had already handed over.
        if (controller.signal.aborted) break;
        if (event.type === "token" && event.text) hasContent = true;
        if (event.type !== "token") finished = true;
        patchAnswer((m) => applyEvent(m, event));
        if (event.type === "error" && !hasContent) restoreDraft();
      }
      if (!finished) throw new StreamIncompleteError();
    } catch (error) {
      const aborted = controller.signal.aborted;
      // The class only: a message can carry a host or a piece of the user's text.
      if (!aborted) {
        logger.error("Assistant turn failed", { error: error instanceof Error ? error.name : typeof error });
      }
      patchAnswer((m) => applyFailure(m, error, aborted, hasContent));
      if (!aborted && !hasContent) restoreDraft();
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
    setThread((prev) => ({ key: prev.key, messages: [] }));
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
