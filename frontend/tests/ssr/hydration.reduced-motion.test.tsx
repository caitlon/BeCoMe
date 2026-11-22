import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import { prefersReducedMotion } from 'framer-motion';
import { publicRoutes } from '@/seo/publicRoutes';
import { renderServerPages, hydrate, type ServerPages } from '@tests/support/hydration';

vi.mock('@/lib/api', () => ({
  api: { getCurrentUser: vi.fn(), setOnSessionExpired: vi.fn(), requestJson: vi.fn() },
}));

// Its own file because framer-motion reads the reduced-motion preference once per process and
// keeps it outside the module graph that vi.resetModules clears: sharing a worker with the
// other hydration tests would make this variant depend on which of them ran first.
afterEach(async () => {
  const { setHydrating } = await import('@/lib/hydration');
  setHydrating(false);
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe.each([false, true])('hydrating the prerendered pages with reduced motion, assistant %s', (assistant) => {
  let pages: ServerPages = {};

  beforeAll(async () => {
    pages = await renderServerPages(assistant);
  }, 60_000);

  it.each([...publicRoutes, '/not-a-page'])('keeps the server HTML of %s', async (url) => {
    const run = await hydrate({
      url,
      html: pages[url],
      assistant,
      matchingQueries: ['prefers-reduced-motion'],
    });
    await run.hydrated();

    // framer-motion has read the preference this variant is about, so the run is not a plain one.
    expect(prefersReducedMotion.current).toBe(true);
    expect(run.errors).toEqual([]);
    expect(run.consoleErrors).toEqual([]);
    expect(run.heading?.isConnected).toBe(true);
  });
});
