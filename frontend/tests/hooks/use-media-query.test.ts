import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMediaQuery } from '@/hooks/use-media-query';

describe('useMediaQuery', () => {
  const originalMatchMedia = globalThis.matchMedia;
  const listeners = new Map<string, EventListener>();

  const mockMatchMedia = (matches: boolean) => ({
    matches,
    media: '',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: (event: string, listener: EventListener) => {
      listeners.set(event, listener);
    },
    removeEventListener: (event: string) => {
      listeners.delete(event);
    },
    dispatchEvent: vi.fn(),
  });

  afterEach(() => {
    listeners.clear();
    globalThis.matchMedia = originalMatchMedia;
  });

  it('returns true when the query matches', () => {
    window.matchMedia = vi.fn().mockImplementation(() => mockMatchMedia(true));

    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'));

    expect(result.current).toBe(true);
  });

  it('returns false when the query does not match', () => {
    window.matchMedia = vi.fn().mockImplementation(() => mockMatchMedia(false));

    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'));

    expect(result.current).toBe(false);
  });

  it('updates when the media query match state changes', () => {
    let currentMatches = false;
    window.matchMedia = vi.fn().mockImplementation(() => ({
      ...mockMatchMedia(currentMatches),
      get matches() {
        return currentMatches;
      },
    }));

    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'));
    expect(result.current).toBe(false);

    act(() => {
      currentMatches = true;
      listeners.get('change')?.(new Event('change'));
    });

    expect(result.current).toBe(true);
  });

  it('cleans up the change listener on unmount', () => {
    const removeEventListenerSpy = vi.fn();
    window.matchMedia = vi.fn().mockImplementation(() => ({
      ...mockMatchMedia(false),
      removeEventListener: removeEventListenerSpy,
    }));

    const { unmount } = renderHook(() => useMediaQuery('(min-width: 1024px)'));
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('returns false when matchMedia is unavailable', () => {
    Object.defineProperty(globalThis, 'matchMedia', {
      writable: true,
      value: undefined,
    });

    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'));

    expect(result.current).toBe(false);
  });
});
