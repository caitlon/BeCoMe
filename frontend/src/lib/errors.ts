/**
 * Typed error taxonomy for API requests.
 *
 * Every error the ApiClient can throw is one of the classes below, each
 * carrying a `kind` discriminant so callers can branch on the failure
 * category without inspecting HTTP status codes directly.
 *
 * A status is not always discriminant enough. `POST /auth/login` answers 403
 * both for an unverified account and for a refused bot check, and those need
 * different screens. The API distinguishes them with a `code` field in the
 * error body (api/middleware/exception_handlers.py::ERROR_CODES), which every
 * error below carries through unchanged. Branch on that, never on the `detail`
 * sentence: the sentence is a server-side constant written for a human, and
 * rewording it must not change what the app does.
 */

/**
 * The code the API sends for every way the Turnstile bot check can refuse a
 * request, an absent token included. One value on purpose: it says which screen
 * to draw without telling a caller what the check saw.
 */
export const TURNSTILE_REFUSED_CODE = 'turnstile_refused';

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

/**
 * Base class for any non-2xx HTTP response. Kept as the general fallback.
 *
 * `code` is the API's machine-readable name for this answer, present only on the
 * errors that have one. Undefined means the response carried no code, which is
 * also what an API deployed before the field existed answers, so a caller
 * reading it must treat "absent" as the behaviour it had before.
 */
export class HttpError extends Error {
  readonly kind: 'client' | 'unauthorized' | 'forbidden' | 'rateLimited' | 'server' = 'client';

  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

export class UnauthorizedError extends HttpError {
  override readonly kind = 'unauthorized' as const;

  constructor(message = 'Unauthorized', code?: string) {
    super(message, 401, code);
  }
}

export class ForbiddenError extends HttpError {
  override readonly kind = 'forbidden' as const;

  constructor(message = 'Forbidden', code?: string) {
    super(message, 403, code);
  }
}

export class RateLimitError extends HttpError {
  override readonly kind = 'rateLimited' as const;

  constructor(
    message = 'Too many requests',
    public readonly retryAfter?: number,
    code?: string
  ) {
    super(message, 429, code);
  }
}

export class ServerError extends HttpError {
  override readonly kind = 'server' as const;

  constructor(message = 'Server error', status = 500, code?: string) {
    super(message, status, code);
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

/**
 * The bot check refused this request, whatever the reason.
 *
 * The one 403 that must never be read as "your account is unverified": the check
 * is fail-closed, so while Cloudflare's siteverify is unreachable every sign-in
 * is refused, and telling those users to confirm an address they confirmed long
 * ago sends them into a resend flow that is guarded too.
 */
export const isTurnstileRefusal = (error: unknown): boolean =>
  error instanceof HttpError && error.code === TURNSTILE_REFUSED_CODE;

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
