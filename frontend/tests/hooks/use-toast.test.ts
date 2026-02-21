import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

vi.mock('@/components/ui/toast', () => ({
  Toast: 'div',
  ToastAction: 'button',
}));

import { reducer, useToast, toast } from '@/hooks/use-toast';

/**
 * Cleanup global toast state between tests.
 * The toast module uses module-level mutable state (memoryState, listeners, toastTimeouts)
 * that persists across tests. Since there's no exported reset API, we create a temporary
 * hook instance to dismiss all toasts and flush pending removal timers.
 */
function cleanupToasts() {
  const { result, unmount } = renderHook(() => useToast());
  act(() => {
    result.current.dismiss();
    vi.runAllTimers();
  });
  unmount();
  vi.useRealTimers();
}

describe('reducer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runAllTimers();
    vi.useRealTimers();
  });

  it('ADD_TOAST adds a toast to the beginning', () => {
    const state = { toasts: [] };
    const newToast = { id: '1', title: 'Test', open: true };

    const result = reducer(state, { type: 'ADD_TOAST', toast: newToast });

    expect(result.toasts).toHaveLength(1);
    expect(result.toasts[0]).toEqual(newToast);
  });

  it('ADD_TOAST enforces TOAST_LIMIT of 1', () => {
    const state = { toasts: [{ id: '1', title: 'Old', open: true }] };
    const newToast = { id: '2', title: 'New', open: true };

    const result = reducer(state, { type: 'ADD_TOAST', toast: newToast });

    expect(result.toasts).toHaveLength(1);
    expect(result.toasts[0].id).toBe('2');
  });

  it('UPDATE_TOAST merges props into matching toast', () => {
    const state = { toasts: [{ id: '1', title: 'Original', open: true }] };

    const result = reducer(state, {
      type: 'UPDATE_TOAST',
      toast: { id: '1', title: 'Updated' },
    });

    expect(result.toasts[0].title).toBe('Updated');
    expect(result.toasts[0].open).toBe(true);
  });

  it('DISMISS_TOAST sets open to false for specific toast', () => {
    const state = { toasts: [{ id: '1', open: true }] };

    const result = reducer(state, { type: 'DISMISS_TOAST', toastId: '1' });

    expect(result.toasts[0].open).toBe(false);
  });

  it('DISMISS_TOAST without toastId dismisses all', () => {
    const state = {
      toasts: [
        { id: '1', open: true },
        { id: '2', open: true },
      ],
    };

    const result = reducer(state, { type: 'DISMISS_TOAST' });

    expect(result.toasts.every((t) => t.open === false)).toBe(true);
  });

  it('REMOVE_TOAST removes specific toast', () => {
    const state = { toasts: [{ id: '1' }] };

    const result = reducer(state, { type: 'REMOVE_TOAST', toastId: '1' });

    expect(result.toasts).toHaveLength(0);
  });

  it('REMOVE_TOAST without toastId clears all', () => {
    const state = { toasts: [{ id: '1' }, { id: '2' }] };

    const result = reducer(state, { type: 'REMOVE_TOAST' });

    expect(result.toasts).toHaveLength(0);
  });

  it('UPDATE_TOAST leaves non-matching toasts unchanged', () => {
    const state = { toasts: [{ id: '1', title: 'Original', open: true }] };

    const result = reducer(state, {
      type: 'UPDATE_TOAST',
      toast: { id: '99', title: 'Nope' },
    });

    expect(result.toasts[0].title).toBe('Original');
  });

  it('DISMISS_TOAST with specific id leaves non-matching toasts open', () => {
    const state = {
      toasts: [
        { id: '1', open: true },
        { id: '2', open: true },
      ],
    };

    const result = reducer(state, { type: 'DISMISS_TOAST', toastId: '1' });

    expect(result.toasts[0].open).toBe(false);
    expect(result.toasts[1].open).toBe(true);
  });
});

describe('toast()', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanupToasts();
  });

  it('returns id, dismiss, and update functions', () => {
    let result!: ReturnType<typeof toast>;
    act(() => {
      result = toast({ title: 'Hello' });
    });

    expect(result.id).toBeDefined();
    expect(typeof result.dismiss).toBe('function');
    expect(typeof result.update).toBe('function');
  });

  it('toast appears in useToast state', () => {
    const { result: hookResult } = renderHook(() => useToast());

    act(() => {
      toast({ title: 'Visible' });
    });

    expect(hookResult.current.toasts).toHaveLength(1);
    expect(hookResult.current.toasts[0].title).toBe('Visible');
  });

  it('update changes toast properties', () => {
    const { result: hookResult } = renderHook(() => useToast());

    let toastResult: ReturnType<typeof toast>;
    act(() => {
      toastResult = toast({ title: 'Original' });
    });

    act(() => {
      toastResult.update({ id: toastResult.id, title: 'Updated' });
    });

    expect(hookResult.current.toasts[0].title).toBe('Updated');
  });

  it('onOpenChange(false) dismisses the toast', () => {
    const { result: hookResult } = renderHook(() => useToast());

    act(() => {
      toast({ title: 'Closable' });
    });

    const toastItem = hookResult.current.toasts[0];

    act(() => {
      toastItem.onOpenChange?.(false);
    });

    expect(hookResult.current.toasts[0].open).toBe(false);
  });

  it('onOpenChange(true) does not dismiss the toast', () => {
    const { result: hookResult } = renderHook(() => useToast());

    act(() => {
      toast({ title: 'Keep Open' });
    });

    const toastItem = hookResult.current.toasts[0];

    act(() => {
      toastItem.onOpenChange?.(true);
    });

    expect(hookResult.current.toasts[0].open).toBe(true);
  });
});

describe('useToast()', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanupToasts();
  });

  it('dismiss sets open to false', () => {
    const { result: hookResult } = renderHook(() => useToast());

    let toastId!: string;
    act(() => {
      toastId = toast({ title: 'Test' }).id;
    });

    act(() => {
      hookResult.current.dismiss(toastId);
    });

    expect(hookResult.current.toasts[0].open).toBe(false);
  });

  it('cleans up listener on unmount', () => {
    const hookA = renderHook(() => useToast());
    const hookB = renderHook(() => useToast());

    hookA.unmount();

    act(() => {
      toast({ title: 'After unmount' });
    });

    expect(hookB.result.current.toasts).toHaveLength(1);
    expect(hookB.result.current.toasts[0].title).toBe('After unmount');

    // hookA's state did not update after unmount
    expect(hookA.result.current.toasts).toHaveLength(0);
  });
});
