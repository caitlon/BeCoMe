import { describe, it, expect, afterEach } from 'vitest';
import { isHydrating, setHydrating, shouldHydrate } from '@/lib/hydration';

describe('hydration flag', () => {
  afterEach(() => setHydrating(false));

  it('is off until the client entry sets it', () => {
    expect(isHydrating()).toBe(false);
  });

  it('can be set and cleared', () => {
    setHydrating(true);
    expect(isHydrating()).toBe(true);

    setHydrating(false);
    expect(isHydrating()).toBe(false);
  });
});

describe('shouldHydrate', () => {
  function rootWith(html: string): HTMLElement {
    const root = document.createElement('div');
    root.innerHTML = html;
    return root;
  }

  it('hydrates prerendered content for an English visitor', () => {
    expect(shouldHydrate(rootWith('<main>About</main>'), 'en')).toBe(true);
  });

  it('mounts fresh for a Czech visitor, whatever the root holds', () => {
    expect(shouldHydrate(rootWith('<main>About</main>'), 'cs')).toBe(false);
  });

  it('mounts fresh when the root is empty, the shell behind a login', () => {
    expect(shouldHydrate(rootWith(''), 'en')).toBe(false);
  });

  it('does not count a text node or whitespace as prerendered content', () => {
    expect(shouldHydrate(rootWith('\n  '), 'en')).toBe(false);
  });
});
