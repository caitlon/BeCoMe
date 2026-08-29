import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Store original location
const originalLocation = window.location;

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock fetch. The cases below describe responses as plain objects and mostly leave
// `headers` out, while a real Response always has one and the client reads the CSRF
// token off it, so fill an empty Headers in where a case did not supply its own.
const mockFetch = vi.fn();
globalThis.fetch = ((...args: Parameters<typeof fetch>) =>
  Promise.resolve(mockFetch(...args)).then((response) =>
    response && typeof response === 'object' && !('headers' in response)
      ? Object.assign(response, { headers: new Headers() })
      : response
  )) as typeof fetch;

/** Builds the response headers for a case that needs the API to hand back a CSRF token. */
function csrfHeaders(token: string): Headers {
  return new Headers({ 'X-CSRF-Token': token });
}

// Import api after mocks are set up
// We need to re-import to get a fresh instance each test
let api: typeof import('@/lib/api').api;
// vi.resetModules() below gives api.ts a fresh copy of '@/lib/errors' too, so an
// error class imported once at module scope would fail instanceof checks against
// errors thrown by the freshly re-imported api. Re-import alongside it instead.
let UnauthorizedError: typeof import('@/lib/errors').UnauthorizedError;

describe('ApiClient', () => {
  beforeEach(async () => {
    vi.resetModules();
    localStorageMock.clear();
    mockFetch.mockReset();
    // The DOM environment keeps document.cookie for the whole file, so a case that
    // plants one would otherwise decide what the next case reads.
    document.cookie = '__Host-csrf_token=; Path=/; Secure; expires=Thu, 01 Jan 1970 00:00:00 GMT';

    // Mock window.location
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });

    // Re-import api (and the matching errors module instance) to get a fresh api client
    const module = await import('@/lib/api');
    api = module.api;
    UnauthorizedError = (await import('@/lib/errors')).UnauthorizedError;
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
    });
    vi.unstubAllEnvs();
  });

  describe('Request Handling', () => {
    it('sends credentials so the session cookie is included, without an Authorization header', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: '1' }),
      });

      await api.getCurrentUser();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ credentials: 'include' })
      );
      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers.Authorization).toBeUndefined();
    });

    it('falls back to the __Host-csrf_token cookie when the API has returned no token yet', async () => {
      // Only reachable same-origin, which is how local development runs: Vite
      // proxies /api/v1, so the cookie belongs to this origin and is readable.
      document.cookie = '__Host-csrf_token=csrf-abc; Path=/; Secure';
      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });

      await api.deleteProject('1');

      const [, options] = mockFetch.mock.calls[0];
      expect((options.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-abc');
    });
  });

  // On every deployed environment the SPA and the API answer on different hosts, so
  // the __Host-csrf_token cookie belongs to the API and document.cookie shows the app
  // nothing. The API repeats the value in an X-CSRF-Token response header, and
  // without picking that up the client cannot produce the header the CSRF check
  // demands, which is a 403 on logout and on every other mutation.
  describe('CSRF token from the response header', () => {
    it('picks the token up from the login response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: csrfHeaders('from-login'),
        json: () => Promise.resolve({ access_token: 'tok', token_type: 'bearer' }),
      });
      await api.login('user@example.com', 'pass');

      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
      await api.deleteProject('1');

      const [, options] = mockFetch.mock.calls[1];
      expect((options.headers as Record<string, string>)['X-CSRF-Token']).toBe('from-login');
    });

    it('recovers the token from the session probe, which is what survives a reload', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: csrfHeaders('from-probe'),
        json: () => Promise.resolve({ id: '1' }),
      });
      await api.getCurrentUser(true);

      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
      await api.deleteProject('1');

      const [, options] = mockFetch.mock.calls[1];
      expect((options.headers as Record<string, string>)['X-CSRF-Token']).toBe('from-probe');
    });

    it('prefers the token the API returned over the cookie', async () => {
      document.cookie = '__Host-csrf_token=cookie-value; Path=/; Secure';
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: csrfHeaders('header-value'),
        json: () => Promise.resolve({ id: '1' }),
      });
      await api.getCurrentUser(true);

      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
      await api.deleteProject('1');

      const [, options] = mockFetch.mock.calls[1];
      expect((options.headers as Record<string, string>)['X-CSRF-Token']).toBe('header-value');
    });

    it('sends the rotated token on the retry after a silent refresh', async () => {
      // A refresh mints a new CSRF cookie, so the retry has to carry the new value
      // or it trades a 401 for a 403.
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Expired' }),
        })
        .mockResolvedValueOnce({ ok: true, status: 200, headers: csrfHeaders('rotated') })
        .mockResolvedValueOnce({ ok: true, status: 204 });

      await api.deleteProject('1');

      const [, retryOptions] = mockFetch.mock.calls[2];
      expect((retryOptions.headers as Record<string, string>)['X-CSRF-Token']).toBe('rotated');
    });

    it('forgets the token on logout so the next account starts clean', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: csrfHeaders('first-session'),
        json: () => Promise.resolve({ access_token: 'tok', token_type: 'bearer' }),
      });
      await api.login('user@example.com', 'pass');

      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
      await api.logout();

      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
      await api.deleteProject('1');

      const [, options] = mockFetch.mock.calls[2];
      expect((options.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined();
    });
  });

  describe('Response Handling', () => {
    it('handles successful JSON response', async () => {
      const userData = { id: '1', email: 'test@example.com' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(userData),
      });

      const result = await api.getCurrentUser();
      expect(result).toEqual(userData);
    });

    it('handles 204 No Content response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      const result = await api.deleteProject('1');
      expect(result).toBeUndefined();
    });

    it('parses error response with string detail', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Bad request message' }),
      });

      await expect(api.getProjects()).rejects.toThrow('Bad request message');
    });

    it('parses error response with validation array detail', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({
            detail: [{ loc: ['body', 'email'], msg: 'Invalid email format', type: 'value_error' }],
          }),
      });

      await expect(api.getProjects()).rejects.toThrow('Invalid email format');
    });

    it('handles JSON parse error gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      await expect(api.getProjects()).rejects.toThrow('An unexpected error occurred');
    });

    it('throws HttpError with correct status for 400', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Bad request' }),
      });

      try {
        await api.getProjects();
        expect.fail('Expected HttpError to be thrown');
      } catch (e: unknown) {
        const err = e as { name: string; status: number; message: string };
        expect(err.name).toBe('HttpError');
        expect(err.status).toBe(400);
        expect(err.message).toBe('Bad request');
      }
    });

    it('throws HttpError with correct status for 403', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: 'Forbidden' }),
      });

      try {
        await api.getProjects();
        expect.fail('Expected HttpError to be thrown');
      } catch (e: unknown) {
        const err = e as { name: string; status: number };
        expect(err.name).toBe('HttpError');
        expect(err.status).toBe(403);
      }
    });

    it('throws HttpError with status for JSON parse failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      try {
        await api.getProjects();
        expect.fail('Expected HttpError to be thrown');
      } catch (e: unknown) {
        const err = e as { name: string; status: number; message: string };
        expect(err.name).toBe('HttpError');
        expect(err.status).toBe(502);
        expect(err.message).toBe('An unexpected error occurred');
      }
    });
  });

  describe('Network Failures', () => {
    it('wraps a rejected fetch in a NetworkError instead of an unhandled rejection', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      const { NetworkError } = await import('@/lib/errors');
      await expect(api.getProjects()).rejects.toBeInstanceOf(NetworkError);
    });
  });

  describe('Silent refresh and retry on 401 (AUD-032)', () => {
    afterEach(() => {
      api.setOnSessionExpired(null);
    });

    it('(a) refreshes the session and retries once, returning the retried result', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({ ok: true, status: 200, json: () => Promise.resolve({}) })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve([{ id: '1' }]),
        });

      const result = await api.getProjects();

      expect(result).toEqual([{ id: '1' }]);
      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(mockFetch.mock.calls[1][0]).toContain('/auth/refresh');
      expect(onSessionExpired).not.toHaveBeenCalled();
      expect(window.location.href).toBe('');
    });

    it('(b) calls onSessionExpired and throws UnauthorizedError when refresh also fails, without a further retry', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Refresh failed' }),
        });

      await expect(api.getProjects()).rejects.toBeInstanceOf(UnauthorizedError);

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
      expect(window.location.href).toBe('');
    });

    it('(c) shares a single in-flight refresh across concurrent 401s and retries every caller', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      let refreshCalls = 0;
      const callCounts: Record<string, number> = {};
      mockFetch.mockImplementation((url: string) => {
        if (url.includes('/auth/refresh')) {
          refreshCalls += 1;
          return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
        }
        callCounts[url] = (callCounts[url] ?? 0) + 1;
        if (callCounts[url] === 1) {
          return Promise.resolve({
            ok: false,
            status: 401,
            json: () => Promise.resolve({ detail: 'Unauthorized' }),
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
      });

      const results = await Promise.all([
        api.getProjects(),
        api.getInvitations(),
        api.getProjectInvitations('proj-1'),
      ]);

      expect(results).toEqual([[], [], []]);
      expect(refreshCalls).toBe(1);
      expect(onSessionExpired).not.toHaveBeenCalled();
    });

    it('(d) does not attempt a second refresh when the retried request is still 401', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({ ok: true, status: 200, json: () => Promise.resolve({}) })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Still unauthorized' }),
        });

      await expect(api.getProjects()).rejects.toBeInstanceOf(UnauthorizedError);

      expect(mockFetch).toHaveBeenCalledTimes(3);
      const refreshCalls = mockFetch.mock.calls.filter(([url]) =>
        String(url).includes('/auth/refresh')
      );
      expect(refreshCalls).toHaveLength(1);
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
    });

    it('(e) dedupes onSessionExpired across N parallel terminal 401s, then re-notifies after a successful request re-arms it', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      const terminal401 = () =>
        Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        });
      mockFetch.mockImplementation(() => terminal401());

      await Promise.all([
        api.getProjects().catch(() => undefined),
        api.getInvitations().catch(() => undefined),
        api.getProjectInvitations('proj-1').catch(() => undefined),
      ]);

      expect(onSessionExpired).toHaveBeenCalledTimes(1);

      // A successful response re-arms the flag.
      mockFetch.mockReset();
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200, json: () => Promise.resolve([]) });
      await api.getProjects();

      // The next terminal-401 round notifies again.
      mockFetch.mockReset();
      mockFetch.mockImplementation(() => terminal401());
      await api.getProjects().catch(() => undefined);

      expect(onSessionExpired).toHaveBeenCalledTimes(2);
    });

    it('(f) surfaces a ServerError instead of a false logout when refresh itself 5xxs', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: 'Refresh backend down' }),
        });

      const { ServerError } = await import('@/lib/errors');
      const error = await api.getProjects().catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onSessionExpired).not.toHaveBeenCalled();
    });

    it('(g) surfaces a NetworkError instead of a false logout when refresh fails at the network level', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockRejectedValueOnce(new TypeError('Failed to fetch'));

      const { NetworkError } = await import('@/lib/errors');
      const error = await api.getProjects().catch((e) => e);

      expect(error).toBeInstanceOf(NetworkError);
      expect(onSessionExpired).not.toHaveBeenCalled();
    });
  });

  describe('Auth probe handling on 401 (AUD-006)', () => {
    it('getCurrentUser(true) logs quietly and does not notify onSessionExpired when refresh also fails', async () => {
      vi.stubEnv('DEV', true);
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);
      const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Refresh failed' }),
        });

      await expect(api.getCurrentUser(true)).rejects.toBeInstanceOf(UnauthorizedError);

      expect(errorSpy).not.toHaveBeenCalled();
      expect(debugSpy).toHaveBeenCalled();
      expect(onSessionExpired).not.toHaveBeenCalled();

      api.setOnSessionExpired(null);
    });

    it('getCurrentUser(true) throws a ServerError, not UnauthorizedError, when refresh 5xxs', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: 'Refresh backend down' }),
        });

      const { ServerError } = await import('@/lib/errors');
      const error = await api.getCurrentUser(true).catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(error).not.toBeInstanceOf(UnauthorizedError);
      expect(onSessionExpired).not.toHaveBeenCalled();

      api.setOnSessionExpired(null);
    });
  });

  describe('Auth Endpoints', () => {
    it('register sends POST to /auth/register', async () => {
      // 202 with a fixed acknowledgement, never a user object: registration no
      // longer creates a session, so the body content is not the caller's concern.
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: () => Promise.resolve({ detail: 'Check your inbox to finish signing up.' }),
      });

      await api.register({
        email: 'new@example.com',
        password: 'password123',
        first_name: 'New',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/register'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            email: 'new@example.com',
            password: 'password123',
            first_name: 'New',
          }),
        })
      );
    });

    it('verifyEmail sends POST to /auth/verify-email with the token, password, and language', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ detail: 'Your email address is confirmed. You can sign in now.' }),
      });

      await api.verifyEmail('a-token', 'CorrectHorse123!', 'en');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/verify-email'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ token: 'a-token', password: 'CorrectHorse123!', language: 'en' }),
        })
      );
    });

    it('verifyEmail throws a ForbiddenError on a wrong password', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: 'Password does not match this link' }),
      });

      const { ForbiddenError } = await import('@/lib/errors');
      await expect(api.verifyEmail('a-token', 'wrong', 'en')).rejects.toBeInstanceOf(ForbiddenError);
    });

    it('resendVerification sends POST to /auth/resend-verification with the email and password', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: () => Promise.resolve({ detail: 'If that address still needs confirming, a new link is on its way.' }),
      });

      await api.resendVerification('user@example.com', 'CorrectHorse123!');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/resend-verification'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'user@example.com', password: 'CorrectHorse123!' }),
        })
      );
    });

    it('login sends a form-urlencoded POST with credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ access_token: 'new-token', token_type: 'bearer' }),
      });

      const result = await api.login('user@example.com', 'password123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/login'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
      );
      expect(result.access_token).toBe('new-token');
    });

    it('login throws an UnauthorizedError on invalid credentials', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Invalid credentials' }),
      });

      await expect(api.login('wrong@example.com', 'wrong')).rejects.toThrow('Invalid credentials');
      await expect(api.login('wrong@example.com', 'wrong')).rejects.toBeInstanceOf(
        UnauthorizedError
      );
    });

    it('login throws a RateLimitError on 429', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 429,
        json: () => Promise.resolve({ detail: 'Too many attempts' }),
        headers: { get: () => null },
      });

      const { RateLimitError } = await import('@/lib/errors');
      await expect(api.login('user@example.com', 'pass')).rejects.toBeInstanceOf(RateLimitError);
    });

    it('login throws a NetworkError when offline', async () => {
      mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));

      const { NetworkError } = await import('@/lib/errors');
      await expect(api.login('user@example.com', 'pass')).rejects.toBeInstanceOf(NetworkError);
    });

    it('logout posts to /auth/logout to clear the server session', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });

      await api.logout();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/logout'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('does not notify onSessionExpired when the session is already expired on logout', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Refresh failed' }),
        });

      await expect(api.logout()).rejects.toBeInstanceOf(UnauthorizedError);

      expect(onSessionExpired).not.toHaveBeenCalled();

      api.setOnSessionExpired(null);
    });

    it('reports a refused logout instead of pretending it worked', async () => {
      // A 403 here used to be swallowed, so the caller could not tell a revoked
      // session from one still very much alive. AuthContext decides what to do
      // about it; the client's job is to say what happened.
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: 'CSRF token missing or invalid' }),
      });

      await expect(api.logout()).rejects.toThrow('CSRF token missing or invalid');
    });
  });

  describe('User Endpoints', () => {
    it('getCurrentUser probes /auth/me, which also returns the CSRF token', async () => {
      const user = { id: '1', email: 'me@example.com' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(user),
      });

      const result = await api.getCurrentUser();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/me'),
        expect.objectContaining({ headers: expect.any(Object) })
      );
      expect(result).toEqual(user);
    });

    it('updateCurrentUser sends PUT to /users/me', async () => {
      const updatedUser = { id: '1', first_name: 'Updated' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(updatedUser),
      });

      await api.updateCurrentUser({ first_name: 'Updated' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ first_name: 'Updated' }),
        })
      );
    });

    it('changePassword sends PUT to /users/me/password', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.changePassword({ current_password: 'old', new_password: 'new' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me/password'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ current_password: 'old', new_password: 'new' }),
        })
      );
    });

    it('deleteAccount sends DELETE to /users/me', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deleteAccount();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('uploadPhoto sends multipart/form-data POST', async () => {
      const updatedUser = { id: '1', photo_url: 'https://example.com/photo.jpg' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(updatedUser),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await api.uploadPhoto(file);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me/photo'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      );
      const [, options] = mockFetch.mock.calls[0];
      expect(options.body).toBeInstanceOf(FormData);
    });

    it('uploadPhoto carries the CSRF token too, though it builds its own request', async () => {
      // The FormData body does not fit the JSON request() contract, so this path
      // assembles its own headers and would otherwise miss the token entirely.
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: csrfHeaders('for-upload'),
        json: () => Promise.resolve({ id: '1' }),
      });
      await api.getCurrentUser(true);

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: '1', photo_url: 'https://example.com/p.jpg' }),
      });
      await api.uploadPhoto(new File(['test'], 'photo.jpg', { type: 'image/jpeg' }));

      const [, options] = mockFetch.mock.calls[1];
      expect((options.headers as Record<string, string>)['X-CSRF-Token']).toBe('for-upload');
    });

    it('deletePhoto sends DELETE to /users/me/photo', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deletePhoto();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me/photo'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Project Endpoints', () => {
    it('getProjects fetches /projects', async () => {
      const projects = [{ id: '1', name: 'Project 1' }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(projects),
      });

      const result = await api.getProjects();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects'),
        expect.any(Object)
      );
      expect(result).toEqual(projects);
    });

    it('getProject fetches /projects/:id', async () => {
      const project = { id: '123', name: 'Single Project' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(project),
      });

      const result = await api.getProject('123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/123'),
        expect.any(Object)
      );
      expect(result).toEqual(project);
    });

    it('createProject sends POST to /projects', async () => {
      const newProject = { id: '1', name: 'New Project' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(newProject),
      });

      const result = await api.createProject({
        name: 'New Project',
        scale_min: 0,
        scale_max: 100,
        scale_unit: '%',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects'),
        expect.objectContaining({
          method: 'POST',
        })
      );
      expect(result).toEqual(newProject);
    });

    it('updateProject sends PUT to /projects/:id', async () => {
      const updated = { id: '1', name: 'Updated Project' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(updated),
      });

      await api.updateProject('1', { name: 'Updated Project' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/1'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ name: 'Updated Project' }),
        })
      );
    });

    it('deleteProject sends DELETE to /projects/:id', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deleteProject('1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('getProjectInvitations calls correct endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve([{ id: 'inv-1' }]),
      });
      const result = await api.getProjectInvitations('proj-1');
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/invitations'),
        expect.any(Object)
      );
      expect(result).toEqual([{ id: 'inv-1' }]);
    });
  });

  describe('Invitation Endpoints', () => {
    it('inviteExpert sends POST to /projects/:id/invite', async () => {
      const invitation = { id: 'inv-1', project_id: 'proj-1' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(invitation),
      });

      await api.inviteExpert('proj-1', 'expert@example.com');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/invite'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'expert@example.com' }),
        })
      );
    });

    it('getInvitations fetches /invitations', async () => {
      const invitations = [{ id: 'inv-1' }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(invitations),
      });

      const result = await api.getInvitations();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/invitations'),
        expect.any(Object)
      );
      expect(result).toEqual(invitations);
    });

    it('acceptInvitation sends POST to /invitations/:id/accept', async () => {
      const project = { id: 'proj-1' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(project),
      });

      await api.acceptInvitation('inv-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/invitations/inv-1/accept'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('declineInvitation sends POST to /invitations/:id/decline', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.declineInvitation('inv-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/invitations/inv-1/decline'),
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  describe('Member Endpoints', () => {
    it('getMembers fetches /projects/:id/members', async () => {
      const members = [{ user_id: '1', role: 'admin' }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(members),
      });

      const result = await api.getMembers('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/members'),
        expect.any(Object)
      );
      expect(result).toEqual(members);
    });

    it('removeMember sends DELETE to /projects/:id/members/:userId', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.removeMember('proj-1', 'user-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/members/user-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('transferOwnership sends POST to /projects/:id/transfer-ownership', async () => {
      const project = { id: 'proj-1', admin_id: 'user-1' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(project),
      });

      const result = await api.transferOwnership('proj-1', 'user-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/transfer-ownership'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ new_admin_id: 'user-1' }),
        })
      );
      expect(result).toEqual(project);
    });
  });

  describe('Opinion Endpoints', () => {
    it('getOpinions fetches /projects/:id/opinions', async () => {
      const opinions = [{ id: 'op-1', lower_bound: 30 }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(opinions),
      });

      const result = await api.getOpinions('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/opinions'),
        expect.any(Object)
      );
      expect(result).toEqual(opinions);
    });

    it('createOrUpdateOpinion sends POST to /projects/:id/opinions', async () => {
      const opinion = { id: 'op-1', lower_bound: 30, peak: 50, upper_bound: 70 };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(opinion),
      });

      await api.createOrUpdateOpinion('proj-1', {
        position: '0',
        lower_bound: 30,
        peak: 50,
        upper_bound: 70,
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/opinions'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ position: '0', lower_bound: 30, peak: 50, upper_bound: 70 }),
        })
      );
    });

    it('deleteOpinion sends DELETE to /projects/:id/opinions', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deleteOpinion('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/opinions'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Upload Photo Error Handling', () => {
    it('throws a ServerError on uploadPhoto 500 response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Server error' }),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      const { ServerError } = await import('@/lib/errors');
      const error = await api.uploadPhoto(file).catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(error.message).toBe('Server error');
    });

    it('throws a RateLimitError with retryAfter on uploadPhoto 429 response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: () => Promise.resolve({ detail: 'Too many uploads' }),
        headers: { get: (name: string) => (name === 'Retry-After' ? '42' : null) },
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      const { RateLimitError } = await import('@/lib/errors');
      const error = await api.uploadPhoto(file).catch((e) => e);

      expect(error).toBeInstanceOf(RateLimitError);
      expect(error.retryAfter).toBe(42);
    });

    it('silently refreshes and retries once on a 401, succeeding without onSessionExpired', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({ ok: true, status: 200, json: () => Promise.resolve({}) })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ id: '1', photo_url: 'url' }),
        });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      const result = await api.uploadPhoto(file);

      expect(result).toEqual({ id: '1', photo_url: 'url' });
      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(onSessionExpired).not.toHaveBeenCalled();
      expect(window.location.href).toBe('');

      api.setOnSessionExpired(null);
    });

    it('throws an UnauthorizedError and calls onSessionExpired instead of redirecting when refresh also fails', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Refresh failed' }),
        });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      const error = await api.uploadPhoto(file).catch((e) => e);

      expect(error).toBeInstanceOf(UnauthorizedError);
      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
      expect(window.location.href).toBe('');

      api.setOnSessionExpired(null);
    });

    it('classifies an uploadPhoto JSON parse failure as a ServerError', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      const { ServerError } = await import('@/lib/errors');
      const error = await api.uploadPhoto(file).catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(error.message).toBe('An unexpected error occurred');
    });

    it('uses the ServerError default message when uploadPhoto error has no detail', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({}),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      const { ServerError } = await import('@/lib/errors');
      const error = await api.uploadPhoto(file).catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(error.message).toBe('Server error');
    });

    it('uploadPhoto sends credentials and no Authorization header', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: '1', photo_url: 'url' }),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await api.uploadPhoto(file);

      const [, options] = mockFetch.mock.calls[0];
      expect(options.credentials).toBe('include');
      expect(options.headers['Authorization']).toBeUndefined();
    });

    it('throws a ServerError instead of a false logout when refresh 5xxs', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: 'Refresh backend down' }),
        });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      const { ServerError } = await import('@/lib/errors');
      const error = await api.uploadPhoto(file).catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onSessionExpired).not.toHaveBeenCalled();

      api.setOnSessionExpired(null);
    });

    it('sends an X-Request-ID header for log/Sentry correlation', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: '1', photo_url: 'url' }),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await api.uploadPhoto(file);

      const [, options] = mockFetch.mock.calls[0];
      expect((options.headers as Record<string, string>)['X-Request-ID']).toBeTruthy();
    });
  });

  describe('Error Detail Edge Cases', () => {
    it('falls back to "Validation error" when detail is empty array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: [] }),
      });

      await expect(api.getProjects()).rejects.toThrow('Validation error');
    });

    it('falls back to "Validation error" when detail array item has no msg', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({
          detail: [{ loc: ['body'], type: 'value_error' }],
        }),
      });

      await expect(api.getProjects()).rejects.toThrow('Validation error');
    });
  });

  describe('Login Error Edge Cases', () => {
    it('classifies an unreadable 500 body as a ServerError, not a credentials error', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      const { ServerError } = await import('@/lib/errors');
      await expect(api.login('user@example.com', 'pass')).rejects.toBeInstanceOf(ServerError);
      await expect(api.login('user@example.com', 'pass')).rejects.not.toThrow(
        'Invalid credentials'
      );
    });

    it('classifies a non-JSON 502 body as a ServerError with the right status', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      const { ServerError } = await import('@/lib/errors');
      const error = await api.login('user@example.com', 'pass').catch((e) => e);
      expect(error).toBeInstanceOf(ServerError);
      expect(error.status).toBe(502);
      expect(error.message).not.toBe('Invalid credentials');
    });

    it('falls back to the UnauthorizedError default message when error.detail is empty', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: '' }),
      });

      await expect(api.login('user@example.com', 'pass')).rejects.toThrow('Unauthorized');
    });
  });

  describe('Results Endpoint', () => {
    it('getResult fetches /projects/:id/result', async () => {
      const result = { best_compromise: { lower: 30, peak: 50, upper: 70 } };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(result),
      });

      const data = await api.getResult('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/result'),
        expect.any(Object)
      );
      expect(data).toEqual(result);
    });

    it('getResult returns null on error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: 'Not enough opinions' }),
      });

      const data = await api.getResult('proj-1');
      expect(data).toBeNull();
    });
  });

  describe('Result Export Endpoint', () => {
    it('fetches the export endpoint with format and lang query params', async () => {
      const blob = new Blob(['data'], { type: 'text/csv' });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        blob: () => Promise.resolve(blob),
      });

      const result = await api.exportProjectResult('proj-1', 'csv', 'cs');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/result/export?format=csv&lang=cs'),
        expect.objectContaining({ credentials: 'include' })
      );
      expect(result).toBe(blob);
    });

    it('throws HttpError with the server detail on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: 'No calculation result to export' }),
      });

      await expect(api.exportProjectResult('proj-1', 'pdf', 'en')).rejects.toThrow(
        'No calculation result to export'
      );
    });

    it('silently refreshes and retries once on a 401, succeeding without onSessionExpired', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);
      const blob = new Blob(['data'], { type: 'application/pdf' });

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({ ok: true, status: 200, json: () => Promise.resolve({}) })
        .mockResolvedValueOnce({ ok: true, status: 200, blob: () => Promise.resolve(blob) });

      const result = await api.exportProjectResult('proj-1', 'pdf', 'en');

      expect(result).toBe(blob);
      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(onSessionExpired).not.toHaveBeenCalled();
      expect(window.location.href).toBe('');

      api.setOnSessionExpired(null);
    });

    it('throws an UnauthorizedError and calls onSessionExpired instead of redirecting when refresh also fails', async () => {
      const onSessionExpired = vi.fn();
      api.setOnSessionExpired(onSessionExpired);

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Refresh failed' }),
        });

      const error = await api.exportProjectResult('proj-1', 'pdf', 'en').catch((e) => e);

      expect(error).toBeInstanceOf(UnauthorizedError);
      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
      expect(window.location.href).toBe('');

      api.setOnSessionExpired(null);
    });

    it('throws a ServerError on a 500 response with a detail message', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Export blew up' }),
      });

      const { ServerError } = await import('@/lib/errors');
      const error = await api.exportProjectResult('proj-1', 'pdf', 'en').catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(error.message).toBe('Export blew up');
    });

    it('classifies an unreadable export error body as a ServerError', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('no json')),
      });

      const { ServerError } = await import('@/lib/errors');
      const error = await api.exportProjectResult('proj-1', 'csv', 'en').catch((e) => e);

      expect(error).toBeInstanceOf(ServerError);
      expect(error.message).toBe('An unexpected error occurred');
    });
  });

  describe('Request ID and Logging', () => {
    it('adds an X-Request-ID header to requests', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: '1' }),
      });

      await api.getCurrentUser();

      const options = mockFetch.mock.calls[0][1] as RequestInit;
      const headers = options.headers as Record<string, string>;
      expect(headers['X-Request-ID']).toBeTruthy();
    });

    it('logs a warning when getResult fails', async () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: 'Not enough opinions' }),
      });

      const data = await api.getResult('proj-1');

      expect(data).toBeNull();
      expect(warnSpy).toHaveBeenCalled();
    });
  });

  describe('getProjects pagination params', () => {
    beforeEach(() => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      });
    });

    it('requests /projects without a query string when no params are given', async () => {
      await api.getProjects();

      const [url] = mockFetch.mock.calls[0];
      expect(url).toMatch(/\/projects$/);
    });

    it('appends limit and offset when provided', async () => {
      await api.getProjects({ limit: 24, offset: 48 });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects?limit=24&offset=48'),
        expect.anything()
      );
    });

    it('appends only the provided param', async () => {
      await api.getProjects({ limit: 10 });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects?limit=10'),
        expect.anything()
      );
    });
  });
});
