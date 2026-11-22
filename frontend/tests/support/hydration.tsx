import { execFile } from 'node:child_process';
import path from 'node:path';
import { promisify } from 'node:util';
import { StrictMode } from 'react';
import { render, waitFor, act } from '@testing-library/react';
import { vi } from 'vitest';

const execFileAsync = promisify(execFile);
const frontendDir = path.resolve(import.meta.dirname, '../..');

export type ServerPages = Record<string, string>;

/**
 * The prerendered HTML of every public route, made by a separate Node process. That process
 * runs under a Czech locale, so a render that followed the machine's language would show.
 */
export async function renderServerPages(assistant: boolean): Promise<ServerPages> {
  const { stdout } = await execFileAsync(
    process.execPath,
    [path.join(frontendDir, 'tests/support/render-server-html.mjs')],
    {
      cwd: frontendDir,
      env: {
        ...process.env,
        LANG: 'cs_CZ.UTF-8',
        LC_ALL: 'cs_CZ.UTF-8',
        VITE_ASSISTANT_ENABLED: assistant ? 'true' : '',
      },
      maxBuffer: 64 * 1024 * 1024,
    },
  );
  return JSON.parse(stdout) as ServerPages;
}

export interface Probe {
  readonly promise: Promise<unknown>;
  readonly resolve: (value: unknown) => void;
  readonly reject: (error: unknown) => void;
}

/** A promise settled from outside, standing in for the session probe or a page chunk. */
export function deferred(): Probe {
  let resolve!: (value: unknown) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<unknown>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  promise.catch(() => {});
  return { promise, resolve, reject };
}

export interface HydrationOptions {
  readonly url: string;
  readonly html: string;
  readonly assistant: boolean;
  /** Value of the stored theme choice, when the visitor made one. */
  readonly storedTheme?: 'light' | 'dark';
  /** Media queries that match, by a substring of the query. */
  readonly matchingQueries?: readonly string[];
  /** Keeps the About chunk from loading until this promise settles, so the page stays dehydrated meanwhile. */
  readonly holdAboutChunk?: Promise<unknown>;
  /** What the session probe waits on; left out, it answers "not signed in" once `hydrated()` is called. */
  readonly probe?: Probe;
}

function stubMatchMedia(matching: readonly string[]): void {
  vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
    matches: matching.some((fragment) => query.includes(fragment)),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    onchange: null,
    dispatchEvent: () => false,
  })));
}

/**
 * Puts server HTML in the page and hydrates the app over it, with a fresh module
 * graph so no lazy page, i18n state or hydration flag survives from an earlier test.
 * Resolves once hydration has run; `errors` and `consoleErrors` hold what React reported.
 */
export async function hydrate(options: HydrationOptions) {
  vi.resetModules();
  vi.stubEnv('VITE_ASSISTANT_ENABLED', options.assistant ? 'true' : '');
  stubMatchMedia(options.matchingQueries ?? []);
  localStorage.clear();
  sessionStorage.clear();
  if (options.storedTheme) localStorage.setItem('become-theme', options.storedTheme);
  document.documentElement.className = '';
  document.body.innerHTML = '';
  globalThis.history.pushState({}, '', options.url);

  // A mock registered with doMock is evaluated again for this module graph, which a plain
  // vi.mock result is not after vi.resetModules: it would hand back the previous test's page,
  // bound to the previous test's AuthContext.
  vi.doUnmock('@/pages/About');
  const hold = options.holdAboutChunk;
  if (hold) {
    vi.doMock('@/pages/About', async () => {
      await hold;
      return vi.importActual('@/pages/About');
    });
  }

  await import('@/i18n');
  const { api } = await import('@/lib/api');
  const { UnauthorizedError } = await import('@/lib/errors');
  const { setHydrating } = await import('@/lib/hydration');
  const { default: App } = await import('@/App');
  const { ThemeProvider } = await import('@/components/ThemeProvider');

  const probe = options.probe ?? deferred();
  vi.mocked(api.getCurrentUser).mockImplementation(() => probe.promise as never);

  const container = document.createElement('div');
  container.innerHTML = options.html;
  document.body.append(container);
  const heading = container.querySelector('h1');

  const errors: unknown[] = [];
  const consoleErrors: string[] = [];
  vi.spyOn(console, 'error').mockImplementation((...args) => {
    consoleErrors.push(args.map(String).join(' '));
  });
  // The 404 page logs the unknown route; that is not what is under test.
  vi.spyOn(console, 'warn').mockImplementation(() => {});

  setHydrating(true);
  render(
    <StrictMode>
      <ThemeProvider defaultTheme="system" storageKey="become-theme">
        <App />
      </ThemeProvider>
    </StrictMode>,
    { container, hydrate: true, onRecoverableError: (error) => errors.push(error) },
  );

  return {
    container,
    heading,
    errors,
    consoleErrors,
    api,
    probe,
    /** Waits until React has taken over the server's node, not replaced it. */
    async hydrated() {
      await waitFor(
        () => {
          expect(heading).not.toBeNull();
          // React puts its fiber on a node it hydrated; a node it threw away never gets one.
          expect(Object.keys(heading as Element).some((key) => key.startsWith('__reactFiber$'))).toBe(true);
        },
        { timeout: 5000 },
      );
      // Answer the session probe (unless the test holds it) and let its updates land.
      await act(async () => {
        if (!options.probe) probe.reject(new UnauthorizedError('Not authenticated'));
        await probe.promise.catch(() => {});
      });
    },
  };
}
