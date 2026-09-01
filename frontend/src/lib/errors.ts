/**
 * Typed error taxonomy for API requests.
 *
 * Every error the ApiClient can throw is one of the classes below, each
 * carrying a `kind` discriminant so callers can branch on the failure
 * category without inspecting HTTP status codes directly.
 */

/** A fetch() call itself failed: offline, DNS failure, CORS, aborted, etc. */
export class NetworkError extends Error {
  readonly kind = 'network' as const;
  readonly cause?: unknown;

  constructor(message = 'Network request failed', options?: { cause?: unknown }) {
    super(message);
    this.name = 'NetworkError';
    this.cause = options?.cause;
  }
}

/** Base class for any non-2xx HTTP response. Kept as the general fallback. */
export class HttpError extends Error {
  readonly kind: 'client' | 'unauthorized' | 'forbidden' | 'rateLimited' | 'server' = 'client';

  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'HttpError';
  }
}

export class UnauthorizedError extends HttpError {
  override readonly kind = 'unauthorized' as const;

  constructor(message = 'Unauthorized') {
    super(message, 401);
  }
}

export class ForbiddenError extends HttpError {
  override readonly kind = 'forbidden' as const;

  constructor(message = 'Forbidden') {
    super(message, 403);
  }
}

export class RateLimitError extends HttpError {
  override readonly kind = 'rateLimited' as const;

  constructor(message = 'Too many requests', public readonly retryAfter?: number) {
    super(message, 429);
  }
}

export class ServerError extends HttpError {
  override readonly kind = 'server' as const;

  constructor(message = 'Server error', status = 500) {
    super(message, status);
  }
}

export type ApiRequestError =
  | NetworkError
  | UnauthorizedError
  | ForbiddenError
  | RateLimitError
  | ServerError
  | HttpError;

export const isNetworkError = (error: unknown): error is NetworkError =>
  error instanceof NetworkError;

export const isUnauthorized = (error: unknown): error is UnauthorizedError =>
  error instanceof UnauthorizedError;

export const isRateLimited = (error: unknown): error is RateLimitError =>
  error instanceof RateLimitError;

export const isServerError = (error: unknown): error is ServerError =>
  error instanceof ServerError;

/** A network hiccup or a 5xx: the service itself is the problem, not the request. */
export const isServiceUnavailable = (error: unknown): boolean =>
  isNetworkError(error) || isServerError(error);

/**
 * Worth retrying automatically: transient network/server failures only.
 *
 * Same predicate as isServiceUnavailable today, kept as a separate name on
 * purpose: "should react-query retry this" and "should the UI show a
 * service-unavailable message" are distinct decisions that may diverge later.
 */
export const isRetryable = (error: unknown): boolean =>
  isNetworkError(error) || isServerError(error);
