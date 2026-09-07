import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

type FakeTurnstileApi = {
  render: ReturnType<typeof vi.fn>;
  reset: ReturnType<typeof vi.fn>;
  remove: ReturnType<typeof vi.fn>;
};

function makeFakeApi(): FakeTurnstileApi {
  return { render: vi.fn(), reset: vi.fn(), remove: vi.fn() };
}

describe('lib/turnstile', () => {
  beforeEach(() => {
    // scriptLoad is module-level state; a fresh module instance per test keeps
    // one test's in-flight script promise from leaking into the next.
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete (window as { turnstile?: unknown }).turnstile;
    document.querySelectorAll('script').forEach((el) => el.remove());
  });

  describe('getTurnstileSiteKey / isTurnstileRequired', () => {
    it('reports no sitekey and no requirement when the build was given none', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', '');
      const { getTurnstileSiteKey, isTurnstileRequired } = await import('@/lib/turnstile');

      expect(getTurnstileSiteKey()).toBe('');
      expect(isTurnstileRequired()).toBe(false);
    });

    it('reports the configured sitekey and that a token is required', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'site-key-123');
      const { getTurnstileSiteKey, isTurnstileRequired } = await import('@/lib/turnstile');

      expect(getTurnstileSiteKey()).toBe('site-key-123');
      expect(isTurnstileRequired()).toBe(true);
    });
  });

  describe('loadTurnstileScript', () => {
    // happy-dom refuses to fetch an external script: by default it throws a DOMException
    // out of document.head.append itself, and opting into
    // handleDisabledFileLoadingAsSuccess just trades that for dispatching `load`
    // immediately on insertion, before the test gets a chance to control the outcome.
    // Neither behaviour is what a browser does, so instead of fighting happy-dom's
    // network stub, these tests intercept the insertion point: document.head.append is
    // redirected into a detached stand-in element, which the loader's script never
    // becomes a document-connected node and so never triggers happy-dom's script-loading
    // special case, while still behaving like a real DOM container for every assertion
    // below (querySelector, remove(), src) and for the `load`/`error` events the tests
    // dispatch by hand.
    let insertedHead: HTMLElement;
    let appendSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      insertedHead = document.createElement('div');
      appendSpy = vi.spyOn(document.head, 'append').mockImplementation((...nodes) => {
        insertedHead.append(...nodes);
      });
    });

    afterEach(() => {
      appendSpy.mockRestore();
    });

    function getInjectedScript(): HTMLScriptElement {
      const script = insertedHead.querySelector('script');
      if (!script) {
        throw new Error('Expected loadTurnstileScript() to have injected a <script> tag');
      }
      return script;
    }

    it('resolves immediately with window.turnstile when the script is already loaded', async () => {
      const existingApi = makeFakeApi();
      (window as unknown as { turnstile: FakeTurnstileApi }).turnstile = existingApi;

      const { loadTurnstileScript } = await import('@/lib/turnstile');

      await expect(loadTurnstileScript()).resolves.toBe(existingApi);
      expect(insertedHead.querySelector('script')).toBeNull();
    });

    it('injects the script once, with explicit render mode, and shares one promise across callers', async () => {
      const { loadTurnstileScript } = await import('@/lib/turnstile');

      const first = loadTurnstileScript();
      const second = loadTurnstileScript();

      const scripts = insertedHead.querySelectorAll('script');
      expect(scripts).toHaveLength(1);
      expect(scripts[0].src).toBe(
        'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
      );

      const api = makeFakeApi();
      (window as unknown as { turnstile: FakeTurnstileApi }).turnstile = api;
      getInjectedScript().dispatchEvent(new Event('load'));

      await expect(first).resolves.toBe(api);
      await expect(second).resolves.toBe(api);
    });

    it('rejects when the script fails to load, and lets a later call try again', async () => {
      const { loadTurnstileScript } = await import('@/lib/turnstile');

      const attempt = loadTurnstileScript();
      getInjectedScript().dispatchEvent(new Event('error'));

      await expect(attempt).rejects.toThrow('Turnstile script failed to load');
      // The dead script is removed rather than left behind for a retry to trip over.
      expect(insertedHead.querySelector('script')).toBeNull();

      const retryApi = makeFakeApi();
      const retry = loadTurnstileScript();
      expect(insertedHead.querySelectorAll('script')).toHaveLength(1);
      (window as unknown as { turnstile: FakeTurnstileApi }).turnstile = retryApi;
      getInjectedScript().dispatchEvent(new Event('load'));

      await expect(retry).resolves.toBe(retryApi);
    });

    it('rejects when the script loads without defining window.turnstile', async () => {
      const { loadTurnstileScript } = await import('@/lib/turnstile');

      const attempt = loadTurnstileScript();
      getInjectedScript().dispatchEvent(new Event('load'));

      await expect(attempt).rejects.toThrow(
        'Turnstile script loaded without defining window.turnstile'
      );
      expect(insertedHead.querySelector('script')).toBeNull();
    });
  });
});
