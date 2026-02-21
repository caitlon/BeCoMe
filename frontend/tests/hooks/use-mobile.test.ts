import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useIsMobile } from '@/hooks/use-mobile';

describe('useIsMobile', () => {
  const originalInnerWidth = window.innerWidth;
  const originalMatchMedia = globalThis.matchMedia;
  const listeners: Map<string, EventListener> = new Map();

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

  beforeEach(() => {
    listeners.clear();
  });

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      value: originalInnerWidth,
    });
    globalThis.matchMedia = originalMatchMedia;
  });

  it('returns false when window width is above 768px', () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1024 });
    window.matchMedia = vi.fn().mockImplementation(() => mockMatchMedia(false));

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(false);
  });

  it('returns true when window width is below 768px', () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 500 });
    window.matchMedia = vi.fn().mockImplementation(() => mockMatchMedia(true));

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(true);
  });

  it('updates when window is resized', () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, value: 1024 });
    window.matchMedia = vi.fn().mockImplementation(() => mockMatchMedia(false));

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(false);

    // Simulate resize to mobile
    act(() => {
      Object.defineProperty(window, 'innerWidth', { writable: true, value: 500 });
      const listener = listeners.get('change');
      if (listener) {
        listener(new Event('change'));
      }
    });

    expect(result.current).toBe(true);
  });

  it('cleans up event listener on unmount', () => {
    const removeEventListenerSpy = vi.fn();
    window.matchMedia = vi.fn().mockImplementation(() => ({
      ...mockMatchMedia(false),
      removeEventListener: removeEventListenerSpy,
    }));

    const { unmount } = renderHook(() => useIsMobile());

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('returns false when matchMedia is undefined', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).matchMedia = undefined;

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(false);
  });
});
