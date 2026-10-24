import { useQuery, type Query, type UseQueryResult } from "@tanstack/react-query";
import { getAssistantConfig } from "./assistant-api";
import type { AssistantConfigResponse } from "@/types/api";
import { HttpError } from "@/lib/errors";
import { shouldRetryQuery } from "@/lib/queryClient";

const isNotFound = (error: unknown): boolean => error instanceof HttpError && error.status === 404;

/** Whether the query may be requested again: every state except a cached 404. */
const mayRequestAgain = (query: Query<AssistantConfigResponse, HttpError>): boolean => !isNotFound(query.state.error);

/**
 * GET /api/v1/assistant/config. A 404 means the backend router was never
 * mounted (assistant_enabled=False server-side) -- that is the expected
 * "feature is off" answer and it is final: the query is not retried and the
 * cached error is not re-requested on window focus, reconnect or remount (for
 * a cached error that takes `retryOnMount`, not `refetchOnMount`).
 *
 * Every other error is asked for again on a later focus, reconnect or remount,
 * so the assistant appears once the server is back without a page reload. A
 * network error or a 5xx is also retried at once under `shouldRetryQuery`.
 * A query with no data counts as stale whatever
 * `staleTime` says, which is what lets those triggers fire. After a success
 * staleTime is infinite because this value cannot change for the life of a
 * session -- the server process would have to restart with a different flag.
 */
export function useAssistantConfig(enabled: boolean): UseQueryResult<AssistantConfigResponse, HttpError> {
  return useQuery<AssistantConfigResponse, HttpError>({
    queryKey: ["assistant", "config"],
    queryFn: getAssistantConfig,
    enabled,
    retry: shouldRetryQuery,
    refetchOnWindowFocus: mayRequestAgain,
    refetchOnReconnect: mayRequestAgain,
    retryOnMount: mayRequestAgain,
    staleTime: Infinity,
  });
}
