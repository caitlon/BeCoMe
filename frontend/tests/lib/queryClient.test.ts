import { describe, it, expect } from 'vitest';
import { createQueryClient, shouldRetryQuery } from '@/lib/queryClient';
import {
  HttpError,
  NetworkError,
  ServerError,
  UnauthorizedError,
  ForbiddenError,
  RateLimitError,
} from '@/lib/errors';

describe('shouldRetryQuery', () => {
  it('does not retry a plain 4xx HttpError', () => {
    expect(shouldRetryQuery(0, new HttpError('Bad request', 400))).toBe(false);
  });

  it('does not retry UnauthorizedError, ForbiddenError, or RateLimitError', () => {
    expect(shouldRetryQuery(0, new UnauthorizedError())).toBe(false);
    expect(shouldRetryQuery(0, new ForbiddenError())).toBe(false);
    expect(shouldRetryQuery(0, new RateLimitError())).toBe(false);
  });

  it('retries a ServerError up to two times', () => {
    const error = new ServerError('Server error', 500);
    expect(shouldRetryQuery(0, error)).toBe(true);
    expect(shouldRetryQuery(1, error)).toBe(true);
    expect(shouldRetryQuery(2, error)).toBe(false);
  });

  it('retries a NetworkError up to two times', () => {
    const error = new NetworkError();
    expect(shouldRetryQuery(0, error)).toBe(true);
    expect(shouldRetryQuery(1, error)).toBe(true);
    expect(shouldRetryQuery(2, error)).toBe(false);
  });

  it('does not retry a plain Error that is neither a NetworkError nor a ServerError', () => {
    expect(shouldRetryQuery(0, new Error('Something odd'))).toBe(false);
  });
});

describe('createQueryClient', () => {
  it('configures staleTime and the retry policy', () => {
    const client = createQueryClient();
    const defaults = client.getDefaultOptions().queries;

    expect(defaults?.staleTime).toBe(30_000);
    expect(defaults?.retry).toBe(shouldRetryQuery);
  });
});
