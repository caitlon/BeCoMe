import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useScrollSpy } from '@/hooks/useScrollSpy';

describe('useScrollSpy', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns defaultId as initial activeId', () => {
    const { result } = renderHook(() =>
      useScrollSpy(['section-a', 'section-b'], 'section-a')
    );

    expect(result.current.activeId).toBe('section-a');
  });

  it('returns scrollToSection function', () => {
    const { result } = renderHook(() =>
      useScrollSpy(['section-a'], 'section-a')
    );

    expect(typeof result.current.scrollToSection).toBe('function');
  });

  it('scrollToSection calls window.scrollTo with smooth behavior', () => {
    vi.spyOn(globalThis, 'scrollTo').mockImplementation(() => {});

    const el = document.createElement('div');
    el.id = 'section-a';
    document.body.appendChild(el);
    vi.spyOn(el, 'getBoundingClientRect').mockReturnValue({
      top: 200, bottom: 400, left: 0, right: 0,
      width: 0, height: 200, x: 0, y: 200, toJSON: () => {},
    });

    const { result } = renderHook(() =>
      useScrollSpy(['section-a'], 'section-a')
    );

    act(() => {
      result.current.scrollToSection('section-a');
    });

    expect(globalThis.scrollTo).toHaveBeenCalledWith(
      expect.objectContaining({ behavior: 'smooth' })
    );

    document.body.removeChild(el);
  });

  it('adds and removes scroll event listener', () => {
    const addSpy = vi.spyOn(globalThis, 'addEventListener');
    const removeSpy = vi.spyOn(globalThis, 'removeEventListener');

    const { unmount } = renderHook(() =>
      useScrollSpy(['section-a'], 'section-a')
    );

    expect(addSpy).toHaveBeenCalledWith('scroll', expect.any(Function));

    unmount();

    expect(removeSpy).toHaveBeenCalledWith('scroll', expect.any(Function));
  });

  it('updates activeId when a section is in the viewport on scroll', () => {
    const elA = document.createElement('div');
    elA.id = 'section-a';
    document.body.appendChild(elA);

    const elB = document.createElement('div');
    elB.id = 'section-b';
    document.body.appendChild(elB);

    vi.spyOn(elA, 'getBoundingClientRect').mockReturnValue({
      top: -500, bottom: -300, left: 0, right: 0,
      width: 0, height: 200, x: 0, y: -500, toJSON: () => {},
    });

    vi.spyOn(elB, 'getBoundingClientRect').mockReturnValue({
      top: 100, bottom: 200, left: 0, right: 0,
      width: 0, height: 100, x: 0, y: 100, toJSON: () => {},
    });

    const { result } = renderHook(() =>
      useScrollSpy(['section-a', 'section-b'], 'section-a')
    );

    act(() => {
      globalThis.dispatchEvent(new Event('scroll'));
    });

    expect(result.current.activeId).toBe('section-b');

    document.body.removeChild(elA);
    document.body.removeChild(elB);
  });

  it('scrollToSection does nothing when element does not exist', () => {
    vi.spyOn(document, 'getElementById').mockReturnValue(null);
    vi.spyOn(globalThis, 'scrollTo').mockImplementation(() => {});

    const { result } = renderHook(() =>
      useScrollSpy(['section-a'], 'section-a')
    );

    act(() => {
      result.current.scrollToSection('nonexistent');
    });

    expect(globalThis.scrollTo).not.toHaveBeenCalled();
  });
});
