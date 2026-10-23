import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';

vi.mock('@/pages/Landing', () => ({ default: () => <div data-testid="landing" /> }));
vi.mock('@/contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
const root = vi.hoisted(() => ({ throws: false }));
vi.mock('@/components/assistant/AssistantRoot', async () => {
  const { useLocation } = await import('react-router');
  function AssistantRootStub() {
    // useLocation throws outside a router, so rendering at all proves the mount point.
    const { pathname } = useLocation();
    if (root.throws) throw new Error('panel failed');
    return <div data-testid="assistant-root">{pathname}</div>;
  }
  return { default: AssistantRootStub };
});

describe('App assistant mount', () => {
  beforeEach(() => {
    vi.resetModules();
    root.throws = false;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('mounts the assistant inside the router and outside the routes in a build with the flag', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
    const { default: App } = await import('@/App');

    render(<App />);

    expect(await screen.findByTestId('assistant-root')).toHaveTextContent('/');
    expect(screen.getByTestId('landing')).toBeInTheDocument();
  });

  it('keeps the app on screen when the assistant fails to render', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
    root.throws = true;
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { default: App } = await import('@/App');

    render(<App />);

    expect(await screen.findByTestId('landing')).toBeInTheDocument();
    expect(screen.queryByTestId('assistant-root')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    consoleError.mockRestore();
  });

  it('mounts nothing of it in a build without the flag', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', '');
    const { default: App } = await import('@/App');

    render(<App />);

    expect(await screen.findByTestId('landing')).toBeInTheDocument();
    expect(screen.queryByTestId('assistant-root')).not.toBeInTheDocument();
  });
});
