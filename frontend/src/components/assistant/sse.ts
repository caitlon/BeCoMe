import type { AssistantChatResponse } from "@/types/api";
import { NetworkError, StreamIncompleteError } from "@/lib/errors";

export type AssistantSseEvent =
  | { readonly type: "token"; readonly text: string }
  | { readonly type: "done"; readonly response: AssistantChatResponse }
  | { readonly type: "error"; readonly code: number; readonly detail: string };

// The backend frames events with "\n" only (api/assistant/sse.py), so "\r\n" is out of scope.
const EVENT_SEPARATOR = "\n\n";

/**
 * Reads the body of POST /assistant/chat/stream (api/assistant/README.md,
 * "Streaming"): `token {text}` pieces, then `done <AssistantChatResponse>` or
 * `error {code, detail}`. Events are separated by a blank line and carry one
 * `data:` line of JSON. A block with an unknown event name, or none, is skipped;
 * a block with a known name and no `data:` line is malformed.
 *
 * `done` and `error` end the stream. A body that closes without either throws
 * StreamIncompleteError, so a connection cut mid-answer is never mistaken for a
 * finished one, and so does a block whose payload is not the JSON shape its event
 * promises (for `done`, the required fields of AssistantChatResponse), since nothing
 * after it can be trusted. A read that fails for any other reason, such as a
 * connection dropped mid-body, throws NetworkError with the original error as its
 * `cause`. Aborting `signal` cancels the reader and throws its AbortError, also for
 * events already buffered, whatever they hold.
 */
export async function* readAssistantSseStream(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal
): AsyncGenerator<AssistantSseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const cancelReader = (): void => {
    reader.cancel().catch(() => undefined);
  };
  signal?.addEventListener("abort", cancelReader, { once: true });

  try {
    for (;;) {
      throwIfAborted(signal);
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch (error) {
        // An abort cancels the reader, which can reject the read it interrupted.
        throwIfAborted(signal);
        throw new NetworkError("The connection broke while the answer was streaming", {
          cause: error,
        });
      }
      throwIfAborted(signal);
      const { done, value } = chunk;
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf(EVENT_SEPARATOR);
      while (boundary !== -1) {
        throwIfAborted(signal);
        const event = parseBlock(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + EVENT_SEPARATOR.length);
        if (event) {
          yield event;
          if (event.type !== "token") return;
        }
        boundary = buffer.indexOf(EVENT_SEPARATOR);
      }
    }
    throw new StreamIncompleteError();
  } finally {
    signal?.removeEventListener("abort", cancelReader);
    cancelReader();
  }
}

function throwIfAborted(signal: AbortSignal | undefined): void {
  if (!signal?.aborted) return;
  const reason: unknown = signal.reason;
  throw reason instanceof DOMException && reason.name === "AbortError"
    ? reason
    : new DOMException("The operation was aborted", "AbortError");
}

function parseBlock(block: string): AssistantSseEvent | null {
  let name: string | null = null;
  let data: string | null = null;

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      name = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      data = line.slice("data:".length).trim();
    }
  }

  switch (name) {
    case "token": {
      const payload = parsePayload(requireData(data, name));
      if (typeof payload.text !== "string") throw malformed(name);
      return { type: "token", text: payload.text };
    }
    case "done": {
      const payload = parsePayload(requireData(data, name));
      if (!isChatResponse(payload)) throw malformed(name);
      return { type: "done", response: payload };
    }
    case "error": {
      const payload = parsePayload(requireData(data, name));
      if (typeof payload.code !== "number" || typeof payload.detail !== "string") {
        throw malformed(name);
      }
      return { type: "error", code: payload.code, detail: payload.detail };
    }
    default:
      return null;
  }
}

function requireData(data: string | null, name: string): string {
  if (data === null) throw malformed(name);
  return data;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isChatResponse(payload: Record<string, unknown>): payload is Record<string, unknown> &
  AssistantChatResponse {
  const { checks } = payload;
  return (
    typeof payload.answer === "string" &&
    Array.isArray(payload.sources) &&
    Array.isArray(payload.tools_used) &&
    isRecord(checks) &&
    typeof checks.citations_valid === "boolean" &&
    typeof checks.numbers_grounded === "boolean" &&
    Array.isArray(checks.ungrounded_numbers) &&
    isRecord(payload.usage) &&
    isRecord(payload.timing)
  );
}

function parsePayload(data: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    throw new StreamIncompleteError("The stream carried an event that is not valid JSON");
  }
  if (!isRecord(parsed)) throw malformed("");
  return parsed;
}

function malformed(name: string): StreamIncompleteError {
  return new StreamIncompleteError(`The stream carried a malformed ${name || "event"} payload`);
}
