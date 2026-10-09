import { api } from "@/lib/api";
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
 * typed error, and aborting `signal` rejects with the AbortError.
 */
export async function streamAssistantMessage(
  request: AssistantChatRequest,
  signal: AbortSignal
): Promise<Response> {
  return api.requestStream("/assistant/chat/stream", {
    method: "POST",
    signal,
    headers: { Accept: "text/event-stream" },
    body: JSON.stringify(request),
  });
}
