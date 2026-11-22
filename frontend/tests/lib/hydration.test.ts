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
  function rootWith(html: string, route?: string): HTMLElement {
    const root = document.createElement('div');
    root.innerHTML = html;
    if (route !== undefined) root.setAttribute('data-route', route);
    return root;
  }

  it('hydrates prerendered content for an English visitor on the route it was rendered for', () => {
    expect(shouldHydrate(rootWith('<main>About</main>', '/about'), 'en', '/about')).toBe(true);
  });

  it('ignores a trailing slash in the location, since nginx serves /about/ the same page', () => {
    expect(shouldHydrate(rootWith('<main>About</main>', '/about'), 'en', '/about/')).toBe(true);
  });

  it('matches the home page with its single slash', () => {
    expect(shouldHydrate(rootWith('<main>Home</main>', '/'), 'en', '/')).toBe(true);
  });

  it('mounts fresh when the page was rendered for another route', () => {
    expect(shouldHydrate(rootWith('<main>About</main>', '/about'), 'en', '/case-study/unknown')).toBe(false);
  });

  it('mounts fresh for the 404 page, which carries no route, whatever the location', () => {
    expect(shouldHydrate(rootWith('<main>404</main>'), 'en', '/whatever')).toBe(false);
    expect(shouldHydrate(rootWith('<main>404</main>'), 'en', '/')).toBe(false);
  });

  it('mounts fresh for a Czech visitor, whatever the root holds', () => {
    expect(shouldHydrate(rootWith('<main>About</main>', '/about'), 'cs', '/about')).toBe(false);
  });

  it('mounts fresh when the root is empty, the shell behind a login', () => {
    expect(shouldHydrate(rootWith(''), 'en', '/projects')).toBe(false);
  });

  it('does not count a text node or whitespace as prerendered content', () => {
    expect(shouldHydrate(rootWith('\n  ', '/about'), 'en', '/about')).toBe(false);
  });
});
