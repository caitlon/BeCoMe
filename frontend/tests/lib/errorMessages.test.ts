import { describe, it, expect } from 'vitest';
import { describeError } from '@/lib/errorMessages';
import {
  NetworkError,
  ServerError,
  RateLimitError,
  UnauthorizedError,
  ForbiddenError,
  HttpError,
  TURNSTILE_REFUSED_CODE,
  CSRF_INVALID_CODE,
  INVALID_CREDENTIALS_CODE,
  DISPOSABLE_EMAIL_DOMAIN_CODE,
  UNRESOLVABLE_EMAIL_DOMAIN_CODE,
  VALUES_OUT_OF_RANGE_CODE,
  SCALE_EXCLUDES_OPINIONS_CODE,
  SCALE_RANGE_INVALID_CODE,
  INVALID_PROJECT_DISPOSITION_CODE,
  ACCOUNT_HAS_OWNED_PROJECTS_CODE,
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
} from '@/lib/errors';

// Identity translator: makes assertions read as "which key was picked",
// independent of the actual English/Czech copy in the i18n JSON files.
const t = (key: string) => key;

// Mimics i18next's {{placeholder}} interpolation, so assertions can verify
// both which key was picked AND that the options were threaded through.
const tInterpolate = (key: string, options?: Record<string, unknown>) => {
  const templates: Record<string, string> = {
    'errors.tooManyAttempts': 'Too many attempts.',
    'errors.tooManyAttemptsRetry': 'Too many attempts. Retry in {{seconds}}s.',
  };
  const template = templates[key] ?? key;
  if (!options) return template;
  return template.replace(/{{(\w+)}}/g, (_match, name: string) => String(options[name] ?? ''));
};

describe('describeError', () => {
  it('maps a NetworkError to the serviceUnavailable key', () => {
    expect(describeError(new NetworkError(), t, 'fallback')).toBe('errors.serviceUnavailable');
  });

  it('maps a ServerError to the serviceUnavailable key', () => {
    expect(describeError(new ServerError(), t, 'fallback')).toBe('errors.serviceUnavailable');
  });

  it('maps a RateLimitError to the tooManyAttempts key', () => {
    expect(describeError(new RateLimitError(), t, 'fallback')).toBe('errors.tooManyAttempts');
  });

  it('includes the retry delay when the RateLimitError carries a retryAfter', () => {
    const result = describeError(new RateLimitError('Too many requests', 30), tInterpolate, 'fallback');
    expect(result).toBe('Too many attempts. Retry in 30s.');
    expect(result).toContain('30');
  });

  it('falls back to the plain tooManyAttempts key when retryAfter is absent', () => {
    expect(describeError(new RateLimitError(), tInterpolate, 'fallback')).toBe(
      'Too many attempts.'
    );
  });

  it('falls back to the plain tooManyAttempts key when retryAfter is not positive', () => {
    expect(describeError(new RateLimitError('Too many requests', 0), tInterpolate, 'fallback')).toBe(
      'Too many attempts.'
    );
  });

  it('maps a refused bot check to its own key, not the server sentence', () => {
    // The API's detail is an English constant. Showing it would put English in a
    // Czech UI and tie the app to wording the server is free to change.
    const refused = new ForbiddenError(
      'Could not confirm you are human. Reload the page and try again.',
      TURNSTILE_REFUSED_CODE
    );
    expect(describeError(refused, t, 'fallback')).toBe('errors.turnstileRefused');
  });

  it.each([
    [INVITEE_NOT_FOUND_CODE, 404, 'errors.inviteeNotFound'],
    [ALREADY_INVITED_CODE, 409, 'errors.alreadyInvited'],
    [ALREADY_MEMBER_CODE, 409, 'errors.alreadyMember'],
    [EXAMPLE_PROJECT_NOT_INVITABLE_CODE, 409, 'errors.exampleProjectNotInvitable'],
    [INVITATION_NOT_FOUND_CODE, 404, 'errors.invitationNotFound'],
    [PHOTO_TYPE_NOT_ALLOWED_CODE, 400, 'errors.photoTypeNotAllowed'],
    [PHOTO_TOO_LARGE_CODE, 400, 'errors.photoTooLarge'],
    [PHOTO_CONTENT_MISMATCH_CODE, 400, 'errors.photoContentMismatch'],
    [PHOTO_UNREADABLE_CODE, 400, 'errors.photoUnreadable'],
    [PHOTO_DIMENSIONS_TOO_LARGE_CODE, 400, 'errors.photoDimensionsTooLarge'],
    [CSRF_INVALID_CODE, 403, 'errors.sessionChanged'],
    [INVALID_CREDENTIALS_CODE, 401, 'errors.invalidCredentials'],
    [DISPOSABLE_EMAIL_DOMAIN_CODE, 400, 'errors.disposableEmailDomain'],
    [UNRESOLVABLE_EMAIL_DOMAIN_CODE, 400, 'errors.unresolvableEmailDomain'],
    [VALUES_OUT_OF_RANGE_CODE, 422, 'errors.valuesOutOfRange'],
    [SCALE_EXCLUDES_OPINIONS_CODE, 409, 'errors.scaleExcludesOpinions'],
    [SCALE_RANGE_INVALID_CODE, 422, 'errors.scaleRangeInvalid'],
    [INVALID_PROJECT_DISPOSITION_CODE, 422, 'errors.invalidProjectDisposition'],
    [ACCOUNT_HAS_OWNED_PROJECTS_CODE, 409, 'errors.accountHasOwnedProjects'],
  ])('maps the %s code (status %s) to the %s key, not the server sentence', (code, status, key) => {
    expect(
      describeError(new HttpError('English server detail', status, code), t, 'fallback')
    ).toBe(key);
  });

  it('keeps the wire value of each refusal code in step with the API', () => {
    expect([
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
      INVALID_PROJECT_DISPOSITION_CODE,
      ACCOUNT_HAS_OWNED_PROJECTS_CODE,
    ]).toEqual([
      'invitee_not_found',
      'already_invited',
      'already_member',
      'example_project_not_invitable',
      'invitation_not_found',
      'photo_type_not_allowed',
      'photo_too_large',
      'photo_content_mismatch',
      'photo_unreadable',
      'photo_dimensions_too_large',
      'csrf_invalid',
      'invalid_credentials',
      'disposable_email_domain',
      'unresolvable_email_domain',
      'values_out_of_range',
      'scale_excludes_opinions',
      'scale_range_invalid',
      'invalid_project_disposition',
      'account_has_owned_projects',
    ]);
  });

  it('lets a service failure or rate limit win over a code carried by the same error', () => {
    expect(
      describeError(new ServerError('boom', 500, INVITEE_NOT_FOUND_CODE), t, 'fallback')
    ).toBe('errors.serviceUnavailable');
    expect(
      describeError(
        new RateLimitError('slow down', undefined, PHOTO_TOO_LARGE_CODE),
        t,
        'fallback'
      )
    ).toBe('errors.tooManyAttempts');
  });

  it.each(['something_else', 'constructor'])(
    'returns the fallback, not the English server message, for a 4xx whose code (%s) is not a known refusal',
    (code) => {
      expect(describeError(new HttpError('Conflict', 409, code), t, 'fallback')).toBe('fallback');
    }
  );

  it('returns the fallback for a 4xx with no code, whatever English detail it carries', () => {
    expect(describeError(new ForbiddenError('Email not verified'), t, 'fallback')).toBe(
      'fallback'
    );
    expect(describeError(new UnauthorizedError('Invalid credentials'), t, 'fallback')).toBe(
      'fallback'
    );
    expect(describeError(new HttpError('Conflict', 409), t, 'fallback')).toBe('fallback');
    expect(describeError(new HttpError('Project not found', 404), t, 'fallback')).toBe('fallback');
  });

  it('uses the error message for a plain Error', () => {
    expect(describeError(new Error('Something broke'), t, 'fallback')).toBe('Something broke');
  });

  it('returns the fallback for a non-Error value', () => {
    expect(describeError('a string was thrown', t, 'fallback')).toBe('fallback');
    expect(describeError(undefined, t, 'fallback')).toBe('fallback');
    expect(describeError({ message: 'not an Error instance' }, t, 'fallback')).toBe('fallback');
  });
});
