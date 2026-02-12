import { describe, it, expect } from 'vitest';
import { cn } from '@/lib/utils';

describe('cn', () => {
  it('merges string classes', () => {
    expect(cn('px-2', 'py-4')).toBe('px-2 py-4');
  });

  it('resolves Tailwind conflicts (last wins)', () => {
    expect(cn('w-full', 'w-32')).toBe('w-32');
  });

  it('handles conditional objects', () => {
    expect(cn({ 'text-red-500': true, 'text-blue-500': false })).toBe('text-red-500');
  });

  it('skips falsy values', () => {
    expect(cn('a', undefined, null, false, 'b')).toBe('a b');
  });

  it('returns empty string for no arguments', () => {
    expect(cn()).toBe('');
  });

  it('handles arrays of classes', () => {
    expect(cn(['px-2', 'py-4'])).toBe('px-2 py-4');
  });
});
