import { describe, it, expect } from 'vitest';
import { createQueryClient, shouldRetryQuery } from '@/lib/queryClient';
import { HttpError } from '@/lib/api';

describe('shouldRetryQuery', () => {
  it('does not retry 4xx responses', () => {
    expect(shouldRetryQuery(0, new HttpError('Not found', 404))).toBe(false);
  });

  it('does not retry 401 responses', () => {
    expect(shouldRetryQuery(0, new HttpError('Unauthorized', 401))).toBe(false);
  });

  it('retries 5xx responses up to two times', () => {
    const error = new HttpError('Server error', 500);
    expect(shouldRetryQuery(0, error)).toBe(true);
    expect(shouldRetryQuery(1, error)).toBe(true);
    expect(shouldRetryQuery(2, error)).toBe(false);
  });

  it('retries network errors up to two times', () => {
    const error = new Error('Network failure');
    expect(shouldRetryQuery(0, error)).toBe(true);
    expect(shouldRetryQuery(1, error)).toBe(true);
    expect(shouldRetryQuery(2, error)).toBe(false);
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
