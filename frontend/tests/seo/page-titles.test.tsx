import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import type { ReactNode } from 'react';
import { notFoundMeta, notFoundPath, pageMeta, publicRoutes } from '@/entry-server';
import { AppWithRouter } from '@/App';
import { ThemeProvider } from '@/components/ThemeProvider';
import i18n from '@/i18n';

vi.mock('@/lib/api', () => ({
  api: { getCurrentUser: vi.fn(), setOnSessionExpired: vi.fn(), requestJson: vi.fn() },
}));

afterEach(() => {
  cleanup();
  document.title = '';
});

async function expectTitleAt(path: string, title: string): Promise<void> {
  await i18n.changeLanguage('en');
  const { api } = await import('@/lib/api');
  // The session probe never answers, so the page stays signed out and loading, as on the server.
  vi.mocked(api.getCurrentUser).mockImplementation(() => new Promise(() => {}));

  const Router = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
  render(
    <ThemeProvider defaultTheme="system" storageKey="become-theme">
      <AppWithRouter Router={Router} />
    </ThemeProvider>,
  );
  await waitFor(() => expect(document.title).toBe(title), { timeout: 5000 });
}

describe('page titles in the prerendered head', () => {
  it.each(publicRoutes)('match the title %s sets in the browser', async (path) => {
    await expectTitleAt(path, pageMeta(path).title);
  });

  it('matches the title the 404 page sets in the browser', async () => {
    await expectTitleAt(notFoundPath, notFoundMeta().title);
  });
});
