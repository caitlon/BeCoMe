import { HttpError, isServiceUnavailable, isRateLimited } from '@/lib/errors';

/**
 * Turns any thrown value into a user-facing message.
 *
 * Network hiccups and 5xx responses get a generic "service unavailable"
 * message rather than whatever text happened to be in the response body,
 * since that body was not written with an end user in mind. Rate limiting
 * gets its own dedicated message. Any other HttpError (401, 409, other 4xx)
 * and plain Error instances use their own message, since those already
 * carry a message meant to be read. Anything else falls back to the
 * caller-supplied default.
 */
export function describeError(
  error: unknown,
  t: (key: string) => string,
  fallback: string
): string {
  if (isServiceUnavailable(error)) {
    return t('errors.serviceUnavailable');
  }
  if (isRateLimited(error)) {
    return t('errors.tooManyAttempts');
  }
  if (error instanceof HttpError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
