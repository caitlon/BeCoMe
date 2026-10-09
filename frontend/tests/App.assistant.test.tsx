import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';

vi.mock('@/pages/Landing', () => ({ default: () => <div data-testid="landing" /> }));
vi.mock('@/contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock('@/components/assistant/AssistantRoot', () => ({
  default: () => <div data-testid="assistant-root" />,
}));

describe('App assistant mount', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('mounts the assistant outside the routed tree in a build with the flag', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
    const { default: App } = await import('@/App');

    render(<App />);

    expect(await screen.findByTestId('assistant-root')).toBeInTheDocument();
    expect(screen.getByTestId('landing')).toBeInTheDocument();
  });

  it('mounts nothing of it in a build without the flag', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', '');
    const { default: App } = await import('@/App');

    render(<App />);

    expect(await screen.findByTestId('landing')).toBeInTheDocument();
    expect(screen.queryByTestId('assistant-root')).not.toBeInTheDocument();
  });
});
