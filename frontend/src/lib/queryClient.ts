import { QueryClient } from "@tanstack/react-query";

import { HttpError } from "@/lib/api";

/**
 * 4xx responses will not succeed on retry, and the ApiClient already
 * redirects to /login on 401 before throwing. Transient 5xx and network
 * failures get two extra attempts.
 */
export const shouldRetryQuery = (failureCount: number, error: Error): boolean =>
  !(error instanceof HttpError && error.status < 500) && failureCount < 2;

export const createQueryClient = (): QueryClient =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: shouldRetryQuery,
      },
    },
  });
