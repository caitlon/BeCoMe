import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { renderHook, act } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';

const { mockNavigate, mockToast } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockToast: vi.fn(),
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

import { useAuthSubmit } from '@/hooks/use-auth-submit';
import { ServerError, RateLimitError } from '@/lib/errors';

const messages = {
  successTitle: 'Success',
  successDescription: 'You are logged in',
  errorTitle: 'Error',
  errorFallback: 'Something went wrong',
};

// describeError() translates via the "common" namespace; without a real i18n
// context, t() just echoes the key back, so these two tests render with the
// actual i18n instance to verify the real English copy is shown.
const i18nWrapper = ({ children }: { children: ReactNode }) =>
  createElement(I18nextProvider, { i18n }, children);

describe('useAuthSubmit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns isLoading false and execute function', () => {
    const { result } = renderHook(() => useAuthSubmit(messages));

    expect(result.current.isLoading).toBe(false);
    expect(typeof result.current.execute).toBe('function');
  });

  it('sets isLoading true during execution', async () => {
    let resolveAction!: () => void;
    const action = () => new Promise<void>((resolve) => { resolveAction = resolve; });

    const { result } = renderHook(() => useAuthSubmit(messages));

    let executePromise: Promise<void>;
    act(() => {
      executePromise = result.current.execute(action);
    });

    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolveAction();
      await executePromise!;
    });

    expect(result.current.isLoading).toBe(false);
  });

  it('calls action, shows success toast, navigates to /projects', async () => {
    const action = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useAuthSubmit(messages));

    await act(async () => {
      await result.current.execute(action);
    });

    expect(action).toHaveBeenCalledOnce();
    expect(mockToast).toHaveBeenCalledWith({
      title: 'Success',
      description: 'You are logged in',
    });
    expect(mockNavigate).toHaveBeenCalledWith('/projects');
  });

  it('shows error toast with error.message on failure', async () => {
    const action = vi.fn().mockRejectedValue(new Error('Invalid credentials'));

    const { result } = renderHook(() => useAuthSubmit(messages));

    await act(async () => {
      await result.current.execute(action);
    });

    expect(mockToast).toHaveBeenCalledWith({
      title: 'Error',
      description: 'Invalid credentials',
      variant: 'destructive',
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows fallback message for non-Error exceptions', async () => {
    const action = vi.fn().mockRejectedValue('network failure');

    const { result } = renderHook(() => useAuthSubmit(messages));

    await act(async () => {
      await result.current.execute(action);
    });

    expect(mockToast).toHaveBeenCalledWith({
      title: 'Error',
      description: 'Something went wrong',
      variant: 'destructive',
    });
  });

  it('shows the service-unavailable message for a ServerError', async () => {
    const action = vi.fn().mockRejectedValue(new ServerError());

    const { result } = renderHook(() => useAuthSubmit(messages), { wrapper: i18nWrapper });

    await act(async () => {
      await result.current.execute(action);
    });

    expect(mockToast).toHaveBeenCalledWith({
      title: 'Error',
      description: 'The service is temporarily unavailable. Please try again in a moment.',
      variant: 'destructive',
    });
  });

  it('shows the too-many-attempts message for a RateLimitError', async () => {
    const action = vi.fn().mockRejectedValue(new RateLimitError());

    const { result } = renderHook(() => useAuthSubmit(messages), { wrapper: i18nWrapper });

    await act(async () => {
      await result.current.execute(action);
    });

    expect(mockToast).toHaveBeenCalledWith({
      title: 'Error',
      description: 'Too many attempts. Please wait a moment and try again.',
      variant: 'destructive',
    });
  });

  it('resets isLoading after error', async () => {
    const action = vi.fn().mockRejectedValue(new Error('fail'));

    const { result } = renderHook(() => useAuthSubmit(messages));

    await act(async () => {
      await result.current.execute(action);
    });

    expect(result.current.isLoading).toBe(false);
  });

  it('drops a re-entrant execute while one is already in flight (double-submit guard)', async () => {
    let resolveAction!: () => void;
    const action = vi.fn(() => new Promise<void>((resolve) => { resolveAction = resolve; }));

    const { result } = renderHook(() => useAuthSubmit(messages));

    // Fire two execute() calls before the first settles; the guard must drop
    // the second so the wrapped action runs exactly once.
    let first!: Promise<void>;
    let second!: Promise<void>;
    act(() => {
      first = result.current.execute(action);
      second = result.current.execute(action);
    });

    expect(action).toHaveBeenCalledOnce();

    await act(async () => {
      resolveAction();
      await Promise.all([first, second]);
    });

    expect(action).toHaveBeenCalledOnce();
  });
});
