import type { AssistantChatResponse } from "@/types/api";
import { StreamIncompleteError } from "@/lib/errors";

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
 * `data:` line of JSON. A block with an unknown event name, or none, is skipped.
 *
 * `done` and `error` end the stream. A body that closes without either throws
 * StreamIncompleteError, so a connection cut mid-answer is never mistaken for a
 * finished one, and so does a block whose payload is not the JSON shape its event
 * promises, since nothing after it can be trusted. Aborting `signal` cancels the
 * reader and throws its AbortError, also for events already buffered.
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
      const { done, value } = await reader.read();
      throwIfAborted(signal);
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf(EVENT_SEPARATOR);
      while (boundary !== -1) {
        const event = parseBlock(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + EVENT_SEPARATOR.length);
        if (event) {
          throwIfAborted(signal);
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

  if (data === null) return null;
  switch (name) {
    case "token": {
      const payload = parsePayload(data);
      if (typeof payload.text !== "string") throw malformed(name);
      return { type: "token", text: payload.text };
    }
    case "done":
      return { type: "done", response: parsePayload(data) as unknown as AssistantChatResponse };
    case "error": {
      const payload = parsePayload(data);
      if (typeof payload.code !== "number" || typeof payload.detail !== "string") {
        throw malformed(name);
      }
      return { type: "error", code: payload.code, detail: payload.detail };
    }
    default:
      return null;
  }
}

function parsePayload(data: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    throw new StreamIncompleteError("The stream carried an event that is not valid JSON");
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw malformed("");
  }
  return parsed as Record<string, unknown>;
}

function malformed(name: string): StreamIncompleteError {
  return new StreamIncompleteError(`The stream carried a malformed ${name || "event"} payload`);
}
