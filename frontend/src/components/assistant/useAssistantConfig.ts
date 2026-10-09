import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getAssistantConfig } from "./assistant-api";
import type { AssistantConfigResponse } from "@/types/api";
import type { HttpError } from "@/lib/errors";

/**
 * GET /api/v1/assistant/config. A 404 means the backend router was never
 * mounted (assistant_enabled=False server-side) -- that is the
 * expected "feature is off" answer, not a transient failure, so this query
 * never retries: retrying a 404 only delays the panel from correctly hiding
 * itself. For the same reason an error (a 404 when the backend has the
 * feature off) is not re-requested on window focus or remount (for a cached
 * error that takes `retryOnMount`, not `refetchOnMount`). staleTime is infinite because this value cannot change for the
 * life of a session -- the server process would have to restart with a
 * different flag.
 */
export function useAssistantConfig(enabled: boolean): UseQueryResult<AssistantConfigResponse, HttpError> {
  return useQuery({
    queryKey: ["assistant", "config"],
    queryFn: getAssistantConfig,
    enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    retryOnMount: false,
    staleTime: Infinity,
  });
}
