import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest';
import { act, cleanup, screen, waitFor } from '@testing-library/react';
import { publicRoutes } from '@/seo/publicRoutes';
import { createUser } from '@tests/factories/user';
import { renderServerPages, hydrate, deferred, type ServerPages } from '@tests/support/hydration';

vi.mock('@/lib/api', () => ({
  api: { getCurrentUser: vi.fn(), setOnSessionExpired: vi.fn(), requestJson: vi.fn() },
}));
// The panel is not what these tests are about; its mounting is the sign that the assistant
// reported itself available.
vi.mock('@/components/assistant/AssistantPanel', () => ({
  AssistantPanel: () => <div data-testid="assistant-panel" />,
}));

const routes = [...publicRoutes, '/not-a-page'];

// What the browser can differ in from the build machine's render, without changing the
// language: the stored theme, the OS colour scheme, the viewport.
const variants = [
  ['light', {}],
  ['stored dark theme', { storedTheme: 'dark' as const }],
  ['dark OS scheme', { matchingQueries: ['prefers-color-scheme: dark'] }],
  ['desktop viewport', { matchingQueries: ['min-width'] }],
] as const;

afterEach(async () => {
  const { setHydrating } = await import('@/lib/hydration');
  setHydrating(false);
  cleanup();
  vi.doUnmock('@/pages/About');
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe.each([false, true])('hydrating the prerendered pages, assistant %s', (assistant) => {
  let pages: ServerPages = {};

  beforeAll(async () => {
    pages = await renderServerPages(assistant);
  }, 60_000);

  describe.each(variants)('%s', (_name, variant) => {
    it.each(routes)('keeps the server HTML of %s', async (url) => {
      const run = await hydrate({ url, html: pages[url], assistant, ...variant });
      await run.hydrated();

      expect(run.errors).toEqual([]);
      expect(run.consoleErrors).toEqual([]);
      expect(run.heading?.isConnected).toBe(true);
    });
  });

  it.each([
    ['a stored dark theme', { storedTheme: 'dark' as const }],
    ['a dark OS scheme', { matchingQueries: ['prefers-color-scheme: dark'] }],
  ])('switches to dark after hydration for %s', async (_name, variant) => {
    const run = await hydrate({ url: '/about', html: pages['/about'], assistant, ...variant });
    await run.hydrated();

    await waitFor(() => expect(document.documentElement).toHaveClass('dark'));
    expect((await screen.findAllByLabelText('Switch to light mode')).length).toBeGreaterThan(0);
    expect(run.heading?.isConnected).toBe(true);
  });

  it('does not mind that the footer year differs from the build year', async () => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2031-06-01T12:00:00Z') });

    const run = await hydrate({ url: '/', html: pages['/'], assistant });
    await run.hydrated();

    expect(run.errors).toEqual([]);
    expect(run.consoleErrors).toEqual([]);
  });

  it('is not fooled: markup that differs from the server HTML is reported', async () => {
    const run = await hydrate({
      url: '/about',
      html: pages['/about'].replace('About BeCoMe', 'Something else'),
      assistant,
    });
    await run.hydrated();

    expect(run.errors.length + run.consoleErrors.length).toBeGreaterThan(0);
  });

  describe('when the session probe answers before the page chunk', () => {
    it('keeps the server HTML of the page', async () => {
      const chunk = deferred();
      const probe = deferred();
      const run = await hydrate({
        url: '/about',
        html: pages['/about'],
        assistant,
        probe,
        holdAboutChunk: chunk.promise,
      });
      const { UnauthorizedError } = await import('@/lib/errors');

      // The page is still dehydrated, waiting for its chunk, when the probe settles.
      await act(async () => {
        probe.reject(new UnauthorizedError('Not authenticated'));
        await probe.promise.catch(() => {});
      });
      expect(Object.keys(run.heading as Element).some((key) => key.startsWith('__reactFiber$'))).toBe(false);
      chunk.resolve(undefined);
      await run.hydrated();

      expect(run.errors).toEqual([]);
      expect(run.consoleErrors).toEqual([]);
      expect(run.heading?.isConnected).toBe(true);
    });
  });

  if (assistant) {
    // The sign-in update is a transition, so it commits only once the held page has hydrated;
    // the assistant's own availability update then arrives with nothing left to discard.
    describe('when a signed-in session and the assistant arrive while the page chunk is held', () => {
      it('keeps the server HTML of the page', async () => {
        const chunk = deferred();
        const probe = deferred();
        const run = await hydrate({
          url: '/about',
          html: pages['/about'],
          assistant,
          probe,
          holdAboutChunk: chunk.promise,
        });
        vi.mocked(run.api.requestJson).mockResolvedValue({
          enabled: true,
          model: 'test',
          mode: 'agent',
          collection: 'test',
          answer_provider: 'local',
          query_provider: 'local',
          embedding_provider: 'local',
        });

        await act(async () => {
          probe.resolve(createUser());
          await probe.promise;
        });
        chunk.resolve(undefined);
        await run.hydrated();
        await screen.findByTestId('assistant-panel');

        expect(run.errors).toEqual([]);
        expect(run.consoleErrors).toEqual([]);
        expect(run.heading?.isConnected).toBe(true);
      });
    });
  }
});
