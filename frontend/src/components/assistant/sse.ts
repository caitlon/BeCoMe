import type { AssistantChatResponse } from "@/types/api";
import { StreamIncompleteError } from "@/lib/errors";

export type AssistantSseEvent =
  | { readonly type: "token"; readonly text: string }
  | { readonly type: "done"; readonly response: AssistantChatResponse }
  | { readonly type: "error"; readonly code: number; readonly detail: string };

const EVENT_SEPARATOR = "\n\n";

/**
 * Reads the body of POST /assistant/chat/stream (api/assistant/README.md,
 * "Streaming"): `token {text}` pieces, then `done <AssistantChatResponse>` or
 * `error {code, detail}`. Events are separated by a blank line and carry one
 * `data:` line of JSON. A block with an unknown event name, or none, is skipped.
 *
 * `done` and `error` end the stream. A body that closes without either throws
 * StreamIncompleteError, so a connection cut mid-answer is never mistaken for a
 * finished one. Aborting `signal` cancels the reader and throws its AbortError.
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
    case "token":
      return { type: "token", text: (JSON.parse(data) as { text: string }).text };
    case "done":
      return { type: "done", response: JSON.parse(data) as AssistantChatResponse };
    case "error": {
      const { code, detail } = JSON.parse(data) as { code: number; detail: string };
      return { type: "error", code, detail };
    }
    default:
      return null;
  }
}
