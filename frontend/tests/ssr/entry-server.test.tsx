// @vitest-environment node
import { describe, it, expect, vi, afterEach } from 'vitest';
import { Window } from 'happy-dom';
import { publicRoutes } from '@/seo/publicRoutes';

// Each render gets a fresh module graph, as a separate prerender process would have, so a
// route's output cannot depend on which routes ran before it.
async function renderRoute(url: string): Promise<string> {
  vi.resetModules();
  const { render } = await import('@/entry-server');
  return render(url);
}

// Parses the server HTML in a separate happy-dom window, so the test file itself stays DOM-free.
function heading(html: string): string {
  const win = new Window();
  win.document.body.innerHTML = html;
  const text = win.document.querySelector('h1')?.textContent?.trim() ?? '';
  void win.happyDOM.close();
  return text;
}

describe('entry-server render', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('runs without a DOM', () => {
    expect(typeof window).toBe('undefined');
    expect(typeof document).toBe('undefined');
  });

  it.each([
    ['/', 'Many expert opinions'],
    ['/about', 'About BeCoMe'],
    ['/docs', 'Documentation'],
    ['/faq', 'Frequently Asked Questions'],
    ['/privacy', 'Privacy'],
    ['/terms', 'Terms of use'],
    ['/case-studies', 'Case Studies'],
    ['/case-study/budget', 'COVID-19 Budget Support'],
    ['/nope', '404'],
  ])('renders %s with its heading and no loader in its place', async (url, expected) => {
    const html = await renderRoute(url);

    expect(heading(html)).toContain(expected);
    // PageLoader is the Suspense fallback of the routed page: its spinner must not stand in for it.
    expect(html).not.toContain('animate-spin');
  });

  it('renders every public route', async () => {
    for (const url of publicRoutes) {
      const html = await renderRoute(url);
      expect(heading(html), url).not.toBe('');
      expect(heading(html), url).not.toBe('404');
    }
  });

  it('gives the same HTML for a route whatever was rendered before it', async () => {
    const alone = await renderRoute('/about');
    await renderRoute('/docs');
    await renderRoute('/case-study/floods');
    expect(await renderRoute('/about')).toBe(alone);
  });

  it('renders English whatever language the build machine reports', async () => {
    vi.stubGlobal('navigator', { language: 'cs-CZ', languages: ['cs-CZ', 'cs'] });

    const html = await renderRoute('/about');

    expect(heading(html)).toBe('About BeCoMe');
    expect(html).not.toContain('O BeCoMe');
  });

  it('does not touch a localStorage global that throws, as newer Node versions expose it', async () => {
    const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('Cannot initialize local storage without a --localstorage-file path');
      },
    });
    try {
      const html = await renderRoute('/about');
      expect(heading(html)).toBe('About BeCoMe');
    } finally {
      if (original) Object.defineProperty(globalThis, 'localStorage', original);
      else Reflect.deleteProperty(globalThis, 'localStorage');
    }
  });

  it('renders signed out, in the default theme, with no session probe', async () => {
    const html = await renderRoute('/');

    expect(html).toContain('Sign In');
    expect(html).toContain('aria-label="Switch to dark mode"');
  });
});
