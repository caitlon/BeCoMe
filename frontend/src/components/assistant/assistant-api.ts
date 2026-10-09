import { api } from "@/lib/api";
import { NetworkError } from "@/lib/errors";
import type { AssistantChatRequest, AssistantConfigResponse } from "@/types/api";

/**
 * GET /api/v1/assistant/config. A thin call through the shared ApiClient
 * singleton's requestJson -- credentials, the CSRF header cache, and the
 * silent-refresh-and-retry on a 401 all come from there, not duplicated here.
 */
export async function getAssistantConfig(): Promise<AssistantConfigResponse> {
  return api.requestJson<AssistantConfigResponse>("/assistant/config");
}

/**
 * POST /api/v1/assistant/chat/stream. Resolves with the open Response once the
 * server has accepted the turn, its body an SSE stream for readAssistantSseStream.
 * A refusal before the stream opens (404, 422, 429, 503) rejects with the usual
 * typed error. Aborting `signal` rejects with an AbortError at any point,
 * including before the response headers arrive: the shared client wraps every
 * fetch rejection as a NetworkError, so the abort is told apart here. A Stop
 * during a pending 401 refresh does not wait for it: the shared refreshSession
 * never observes the signal, so the call is raced against the signal and the
 * refresh runs on for its other callers.
 */
export async function streamAssistantMessage(
  request: AssistantChatRequest,
  signal: AbortSignal
): Promise<Response> {
  try {
    const pending = api.requestStream("/assistant/chat/stream", {
      method: "POST",
      signal,
      headers: { Accept: "text/event-stream" },
      body: JSON.stringify(request),
    });
    // If the abort wins the race, `pending` is still in flight and its later
    // rejection would go unhandled.
    pending.catch(() => undefined);
    return await Promise.race([pending, rejectOnAbort(signal)]);
  } catch (error) {
    if (!signal.aborted) throw error;
    const cause = error instanceof NetworkError ? error.cause : error;
    throw cause instanceof DOMException && cause.name === "AbortError"
      ? cause
      : new DOMException("The operation was aborted", "AbortError");
  }
}

function rejectOnAbort(signal: AbortSignal): Promise<never> {
  return new Promise<never>((_resolve, reject) => {
    const abort = (): void => reject(new DOMException("The operation was aborted", "AbortError"));
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}
