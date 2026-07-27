import { QueryClient } from "@tanstack/react-query";

import { isRetryable } from "@/lib/errors";

/**
 * 4xx responses will not succeed on retry, and a 401 is already handled by
 * the ApiClient's silent-refresh flow before it ever reaches here. Transient
 * failures -- a NetworkError or a ServerError (5xx) -- get two extra attempts.
 */
export const shouldRetryQuery = (failureCount: number, error: Error): boolean =>
  isRetryable(error) && failureCount < 2;

export const createQueryClient = (): QueryClient =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: shouldRetryQuery,
      },
    },
  });
