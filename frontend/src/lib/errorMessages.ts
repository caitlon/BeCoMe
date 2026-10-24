import {
  HttpError,
  isServiceUnavailable,
  isRateLimited,
  isTurnstileRefusal,
  INVITEE_NOT_FOUND_CODE,
  ALREADY_INVITED_CODE,
  ALREADY_MEMBER_CODE,
  EXAMPLE_PROJECT_NOT_INVITABLE_CODE,
  INVITATION_NOT_FOUND_CODE,
  PHOTO_TYPE_NOT_ALLOWED_CODE,
  PHOTO_TOO_LARGE_CODE,
  PHOTO_CONTENT_MISMATCH_CODE,
  PHOTO_UNREADABLE_CODE,
  PHOTO_DIMENSIONS_TOO_LARGE_CODE,
  CSRF_INVALID_CODE,
  INVALID_CREDENTIALS_CODE,
  DISPOSABLE_EMAIL_DOMAIN_CODE,
  UNRESOLVABLE_EMAIL_DOMAIN_CODE,
  VALUES_OUT_OF_RANGE_CODE,
  SCALE_EXCLUDES_OPINIONS_CODE,
  SCALE_RANGE_INVALID_CODE,
} from '@/lib/errors';

/**
 * Translation key (in the common namespace) for each refusal the API names with
 * a `code`. The `detail` beside it is an English server-side constant, so these
 * are what a Czech user reads instead.
 */
const REFUSAL_MESSAGE_KEYS: Record<string, string> = {
  [INVITEE_NOT_FOUND_CODE]: 'errors.inviteeNotFound',
  [ALREADY_INVITED_CODE]: 'errors.alreadyInvited',
  [ALREADY_MEMBER_CODE]: 'errors.alreadyMember',
  [EXAMPLE_PROJECT_NOT_INVITABLE_CODE]: 'errors.exampleProjectNotInvitable',
  [INVITATION_NOT_FOUND_CODE]: 'errors.invitationNotFound',
  [PHOTO_TYPE_NOT_ALLOWED_CODE]: 'errors.photoTypeNotAllowed',
  [PHOTO_TOO_LARGE_CODE]: 'errors.photoTooLarge',
  [PHOTO_CONTENT_MISMATCH_CODE]: 'errors.photoContentMismatch',
  [PHOTO_UNREADABLE_CODE]: 'errors.photoUnreadable',
  [PHOTO_DIMENSIONS_TOO_LARGE_CODE]: 'errors.photoDimensionsTooLarge',
  [CSRF_INVALID_CODE]: 'errors.sessionChanged',
  [INVALID_CREDENTIALS_CODE]: 'errors.invalidCredentials',
  [DISPOSABLE_EMAIL_DOMAIN_CODE]: 'errors.disposableEmailDomain',
  [UNRESOLVABLE_EMAIL_DOMAIN_CODE]: 'errors.unresolvableEmailDomain',
  [VALUES_OUT_OF_RANGE_CODE]: 'errors.valuesOutOfRange',
  [SCALE_EXCLUDES_OPINIONS_CODE]: 'errors.scaleExcludesOpinions',
  [SCALE_RANGE_INVALID_CODE]: 'errors.scaleRangeInvalid',
};

/**
 * Turns any thrown value into a user-facing message.
 *
 * Network hiccups and 5xx responses get a generic "service unavailable"
 * message rather than whatever text happened to be in the response body,
 * since that body was not written with an end user in mind. Rate limiting
 * gets its own dedicated message, including the server-provided retry delay
 * when one is known. A refused bot check gets its own too: its `detail` is an
 * English server-side constant, and what the user needs to be told is that the
 * check did not go through, not whatever the API happened to say. The same goes
 * for every refusal the API names with a `code` (an unknown invitee, a photo that
 * is too large, and so on): each gets a translated line of its own. Any other
 * HttpError (a 4xx with no code, or one this map does not know) gets the
 * caller-supplied default as well, never its own message: the server `detail` is
 * always English, so showing it is the bug this function exists to prevent, while
 * the default is the caller's already translated line. A plain Error keeps its own
 * message. Anything else falls back to the caller-supplied default.
 *
 * `t` must resolve keys in the common namespace, where the `errors.*` lines live.
 */
export function describeError(
  error: unknown,
  t: (key: string, options?: Record<string, unknown>) => string,
  fallback: string
): string {
  if (isServiceUnavailable(error)) {
    return t('errors.serviceUnavailable');
  }
  if (isRateLimited(error)) {
    if (typeof error.retryAfter === 'number' && error.retryAfter > 0) {
      return t('errors.tooManyAttemptsRetry', { seconds: error.retryAfter });
    }
    return t('errors.tooManyAttempts');
  }
  // Order matters, and the branches below cannot be swapped: a refused bot
  // check IS an HttpError, so the generic branch would claim it first and show
  // the server's own English detail instead of a translated line telling the
  // user what to do. The same holds for every coded refusal. A test covers this
  // ordering.
  if (isTurnstileRefusal(error)) {
    return t('errors.turnstileRefused');
  }
  if (
    error instanceof HttpError &&
    error.code &&
    Object.prototype.hasOwnProperty.call(REFUSAL_MESSAGE_KEYS, error.code)
  ) {
    return t(REFUSAL_MESSAGE_KEYS[error.code]);
  }
  if (error instanceof HttpError) {
    return fallback;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
