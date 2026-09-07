import { describe, it, expect, vi } from 'vitest';
import {
  NetworkError,
  HttpError,
  UnauthorizedError,
  ForbiddenError,
  RateLimitError,
  ServerError,
  isNetworkError,
  isUnauthorized,
  isRateLimited,
  isServerError,
  isServiceUnavailable,
  isRetryable,
  isTurnstileRefusal,
  TURNSTILE_REFUSED_CODE,
} from '@/lib/errors';
import { toHttpError, safeFetch } from '@/lib/api';

/** Minimal fetch Response stand-in: only the members toHttpError/safeFetch touch. */
function mockResponse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {}
): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
    headers: { get: (name: string) => headers[name] ?? null },
  } as unknown as Response;
}

describe('NetworkError', () => {
  it('defaults to a generic message', () => {
    const error = new NetworkError();
    expect(error.message).toBe('Network request failed');
    expect(error.kind).toBe('network');
    expect(error.name).toBe('NetworkError');
    expect(error).toBeInstanceOf(Error);
  });

  it('accepts a custom message and exposes the cause', () => {
    const cause = new TypeError('Failed to fetch');
    const error = new NetworkError('Offline', { cause });
    expect(error.message).toBe('Offline');
    expect(error.cause).toBe(cause);
  });
});

describe('HttpError', () => {
  it('stores the message and status, defaulting kind to client', () => {
    const error = new HttpError('Bad request', 400);
    expect(error.message).toBe('Bad request');
    expect(error.status).toBe(400);
    expect(error.kind).toBe('client');
    expect(error.name).toBe('HttpError');
    expect(error).toBeInstanceOf(Error);
  });
});

describe('UnauthorizedError', () => {
  it('defaults message and fixes status to 401', () => {
    const error = new UnauthorizedError();
    expect(error.message).toBe('Unauthorized');
    expect(error.status).toBe(401);
    expect(error.kind).toBe('unauthorized');
    expect(error).toBeInstanceOf(HttpError);
  });

  it('accepts a custom message', () => {
    expect(new UnauthorizedError('Invalid credentials').message).toBe('Invalid credentials');
  });
});

describe('ForbiddenError', () => {
  it('defaults message and fixes status to 403', () => {
    const error = new ForbiddenError();
    expect(error.message).toBe('Forbidden');
    expect(error.status).toBe(403);
    expect(error.kind).toBe('forbidden');
    expect(error).toBeInstanceOf(HttpError);
  });
});

describe('RateLimitError', () => {
  it('defaults message and fixes status to 429', () => {
    const error = new RateLimitError();
    expect(error.message).toBe('Too many requests');
    expect(error.status).toBe(429);
    expect(error.kind).toBe('rateLimited');
    expect(error.retryAfter).toBeUndefined();
    expect(error).toBeInstanceOf(HttpError);
  });

  it('carries an optional retryAfter', () => {
    const error = new RateLimitError('Slow down', 30);
    expect(error.retryAfter).toBe(30);
  });
});

describe('ServerError', () => {
  it('defaults message and status to 500', () => {
    const error = new ServerError();
    expect(error.message).toBe('Server error');
    expect(error.status).toBe(500);
    expect(error.kind).toBe('server');
    expect(error).toBeInstanceOf(HttpError);
  });

  it('accepts a custom status for other 5xx codes', () => {
    const error = new ServerError('Bad gateway', 502);
    expect(error.status).toBe(502);
  });
});

describe('type guards', () => {
  it('isNetworkError only matches NetworkError', () => {
    expect(isNetworkError(new NetworkError())).toBe(true);
    expect(isNetworkError(new ServerError())).toBe(false);
    expect(isNetworkError(new Error('plain'))).toBe(false);
  });

  it('isUnauthorized only matches UnauthorizedError', () => {
    expect(isUnauthorized(new UnauthorizedError())).toBe(true);
    expect(isUnauthorized(new ForbiddenError())).toBe(false);
    expect(isUnauthorized(new HttpError('x', 401))).toBe(false);
  });

  it('isRateLimited only matches RateLimitError', () => {
    expect(isRateLimited(new RateLimitError())).toBe(true);
    expect(isRateLimited(new HttpError('x', 429))).toBe(false);
  });

  it('isServerError only matches ServerError', () => {
    expect(isServerError(new ServerError())).toBe(true);
    expect(isServerError(new HttpError('x', 500))).toBe(false);
  });

  it('isServiceUnavailable matches network and server errors only', () => {
    expect(isServiceUnavailable(new NetworkError())).toBe(true);
    expect(isServiceUnavailable(new ServerError())).toBe(true);
    expect(isServiceUnavailable(new UnauthorizedError())).toBe(false);
    expect(isServiceUnavailable(new HttpError('x', 400))).toBe(false);
    expect(isServiceUnavailable(new Error('plain'))).toBe(false);
  });

  it('isRetryable matches network and server errors only', () => {
    expect(isRetryable(new NetworkError())).toBe(true);
    expect(isRetryable(new ServerError())).toBe(true);
    expect(isRetryable(new RateLimitError())).toBe(false);
    expect(isRetryable(new ForbiddenError())).toBe(false);
  });
});

describe('toHttpError / safeFetch (api.ts error production)', () => {
  it('maps 401 to UnauthorizedError', async () => {
    const error = await toHttpError(mockResponse(401, { detail: 'Not logged in' }));
    expect(error).toBeInstanceOf(UnauthorizedError);
    expect(error.kind).toBe('unauthorized');
    expect(error.status).toBe(401);
    expect(error.message).toBe('Not logged in');
  });

  it('maps 403 to ForbiddenError', async () => {
    const error = await toHttpError(mockResponse(403, { detail: 'No access' }));
    expect(error).toBeInstanceOf(ForbiddenError);
    expect(error.kind).toBe('forbidden');
    expect(error.status).toBe(403);
    expect(error.message).toBe('No access');
  });

  it('maps 429 to RateLimitError and reads Retry-After', async () => {
    const error = await toHttpError(
      mockResponse(429, { detail: 'Slow down' }, { 'Retry-After': '30' })
    );
    expect(error).toBeInstanceOf(RateLimitError);
    expect(error.kind).toBe('rateLimited');
    expect(error.status).toBe(429);
    expect((error as RateLimitError).retryAfter).toBe(30);
  });

  it('maps 429 without a Retry-After header to an undefined retryAfter', async () => {
    const error = await toHttpError(mockResponse(429, { detail: 'Slow down' }));
    expect((error as RateLimitError).retryAfter).toBeUndefined();
  });

  it('maps 5xx to ServerError, preserving the exact status', async () => {
    const error = await toHttpError(mockResponse(502, { detail: 'Bad gateway' }));
    expect(error).toBeInstanceOf(ServerError);
    expect(error.kind).toBe('server');
    expect(error.status).toBe(502);
    expect(error.message).toBe('Bad gateway');
  });

  it('maps other 4xx statuses to a plain client HttpError', async () => {
    const error = await toHttpError(mockResponse(400, { detail: 'Bad request' }));
    expect(error).not.toBeInstanceOf(UnauthorizedError);
    expect(error).not.toBeInstanceOf(ForbiddenError);
    expect(error).not.toBeInstanceOf(RateLimitError);
    expect(error).not.toBeInstanceOf(ServerError);
    expect(error.kind).toBe('client');
    expect(error.status).toBe(400);
    expect(error.message).toBe('Bad request');
  });

  it('falls back to a sensible default message when the body has no detail', async () => {
    const error = await toHttpError(mockResponse(401, {}));
    expect(error.message).toBe('Unauthorized');
  });

  it('safeFetch returns the response unchanged on success', async () => {
    const response = mockResponse(200, { ok: true });
    const fetchMock = vi.fn().mockResolvedValue(response);
    globalThis.fetch = fetchMock;

    const result = await safeFetch('https://example.test/x', {});
    expect(result).toBe(response);
  });

  it('safeFetch wraps a rejected fetch in a NetworkError', async () => {
    const cause = new TypeError('Failed to fetch');
    const fetchMock = vi.fn().mockRejectedValue(cause);
    globalThis.fetch = fetchMock;

    await expect(safeFetch('https://example.test/x', {})).rejects.toBeInstanceOf(NetworkError);
    await expect(safeFetch('https://example.test/x', {})).rejects.toMatchObject({ cause });
  });
});

describe('the code the API sends beside the detail', () => {
  it('carries onto the typed error', async () => {
    const error = await toHttpError(
      mockResponse(403, { detail: 'Could not confirm you are human.', code: 'turnstile_refused' })
    );
    expect(error).toBeInstanceOf(ForbiddenError);
    expect(error.code).toBe('turnstile_refused');
  });

  it('is undefined when the body carries none, as an older API answers', async () => {
    const error = await toHttpError(mockResponse(403, { detail: 'Email address not verified.' }));
    expect(error).toBeInstanceOf(ForbiddenError);
    expect(error.code).toBeUndefined();
  });

  it('is undefined when the body is not JSON at all', async () => {
    const response = {
      status: 403,
      ok: false,
      json: () => Promise.reject(new SyntaxError('not json')),
      headers: { get: () => null },
    } as unknown as Response;

    const error = await toHttpError(response);
    expect(error.code).toBeUndefined();
    expect(error.message).toBe('An unexpected error occurred');
  });

  it('is undefined when the body carries something that is not a string', async () => {
    const error = await toHttpError(mockResponse(403, { detail: 'No access', code: 42 }));
    expect(error.code).toBeUndefined();
  });

  it('survives every status the taxonomy branches on', async () => {
    const bodies = { detail: 'refused', code: 'some_code' };
    expect((await toHttpError(mockResponse(401, bodies))).code).toBe('some_code');
    expect((await toHttpError(mockResponse(429, bodies))).code).toBe('some_code');
    expect((await toHttpError(mockResponse(503, bodies))).code).toBe('some_code');
    expect((await toHttpError(mockResponse(409, bodies))).code).toBe('some_code');
  });

  it('reaches the error built from a validation-array body', async () => {
    const error = await toHttpError(
      mockResponse(422, {
        detail: [{ loc: ['body', 'email'], msg: 'not an email', type: 'value_error' }],
        code: 'some_code',
      })
    );
    expect(error.message).toBe('not an email');
    expect(error.code).toBe('some_code');
  });

  it('reaches the error built from a body with no detail field', async () => {
    const error = await toHttpError(mockResponse(403, { code: 'turnstile_refused' }));
    expect(error.message).toBe('Forbidden');
    expect(error.code).toBe('turnstile_refused');
  });
});

describe('isTurnstileRefusal', () => {
  it('recognises the 403 the bot check answers with', () => {
    expect(isTurnstileRefusal(new ForbiddenError('refused', TURNSTILE_REFUSED_CODE))).toBe(true);
  });

  it('rejects the unverified-account 403, which carries no code', () => {
    // The whole point of the predicate: these two share a status and a class, and
    // reading one as the other tells a verified user their account is unconfirmed.
    expect(isTurnstileRefusal(new ForbiddenError('Email address not verified.'))).toBe(false);
  });

  it('rejects an error carrying some other code', () => {
    expect(isTurnstileRefusal(new ForbiddenError('nope', 'something_else'))).toBe(false);
  });

  it('rejects values that are not HTTP errors at all', () => {
    expect(isTurnstileRefusal(new NetworkError())).toBe(false);
    expect(isTurnstileRefusal('turnstile_refused')).toBe(false);
    expect(isTurnstileRefusal(undefined)).toBe(false);
  });
});
