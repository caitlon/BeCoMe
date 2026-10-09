import { api } from "@/lib/api";
import type { AssistantConfigResponse } from "@/types/api";

/**
 * GET /api/v1/assistant/config. A thin call through the shared ApiClient
 * singleton's requestJson -- credentials, the CSRF header cache, and the
 * silent-refresh-and-retry on a 401 all come from there, not duplicated here.
 */
export async function getAssistantConfig(): Promise<AssistantConfigResponse> {
  return api.requestJson<AssistantConfigResponse>("/assistant/config");
}
