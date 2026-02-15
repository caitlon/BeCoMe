import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

const { mockNavigate, mockToast } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockToast: vi.fn(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

import { useAuthSubmit } from '@/hooks/use-auth-submit';

const messages = {
  successTitle: 'Success',
  successDescription: 'You are logged in',
  errorTitle: 'Error',
  errorFallback: 'Something went wrong',
};

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

  it('resets isLoading after error', async () => {
    const action = vi.fn().mockRejectedValue(new Error('fail'));

    const { result } = renderHook(() => useAuthSubmit(messages));

    await act(async () => {
      await result.current.execute(action);
    });

    expect(result.current.isLoading).toBe(false);
  });
});
