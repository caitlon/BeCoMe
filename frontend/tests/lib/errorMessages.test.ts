import { describe, it, expect } from 'vitest';
import { describeError } from '@/lib/errorMessages';
import {
  NetworkError,
  ServerError,
  RateLimitError,
  UnauthorizedError,
  HttpError,
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

  it('uses the error message for other HttpError instances (401, 409, etc.)', () => {
    expect(describeError(new UnauthorizedError('Invalid credentials'), t, 'fallback')).toBe(
      'Invalid credentials'
    );
    expect(describeError(new HttpError('Conflict', 409), t, 'fallback')).toBe('Conflict');
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
