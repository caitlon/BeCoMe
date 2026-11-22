import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

describe('useDocumentTitle', () => {
  it('sets document title with suffix when title provided', () => {
    renderHook(() => useDocumentTitle('Projects'));

    expect(document.title).toBe('Projects - BeCoMe');
  });

  it('sets document title to "BeCoMe" when title is empty', () => {
    renderHook(() => useDocumentTitle(''));

    expect(document.title).toBe('BeCoMe');
  });

  it('updates document title when title changes', () => {
    const { rerender } = renderHook(
      ({ title }) => useDocumentTitle(title),
      { initialProps: { title: 'Projects' } }
    );

    expect(document.title).toBe('Projects - BeCoMe');

    rerender({ title: 'Profile' });

    expect(document.title).toBe('Profile - BeCoMe');
  });

  it('preserves last title on unmount', () => {
    const { unmount } = renderHook(() => useDocumentTitle('Projects'));

    expect(document.title).toBe('Projects - BeCoMe');

    unmount();

    expect(document.title).toBe('Projects - BeCoMe');
  });

  it('omits the suffix when suffix is false', () => {
    renderHook(() => useDocumentTitle('BeCoMe - Best Compromise Mean', { suffix: false }));

    expect(document.title).toBe('BeCoMe - Best Compromise Mean');
  });

  it('still sets "BeCoMe" for an empty title when suffix is false', () => {
    renderHook(() => useDocumentTitle('', { suffix: false }));

    expect(document.title).toBe('BeCoMe');
  });
});
