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
