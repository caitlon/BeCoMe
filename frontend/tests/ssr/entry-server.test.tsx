// @vitest-environment node
import { describe, it, expect, vi, afterEach } from 'vitest';
import { Window } from 'happy-dom';
import { publicRoutes, publicRouteMeta } from '@/seo/publicRoutes';

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

  it.each([
    ['an error', new Error('boom')],
    ['a thrown string', 'boom'],
  ])('rejects when a page fails inside Suspense with %s, instead of shipping the fallback', async (_name, thrown) => {
    vi.resetModules();
    vi.doMock('@/pages/About', () => ({
      default: () => {
        throw thrown;
      },
    }));
    try {
      const { render } = await import('@/entry-server');
      await expect(render('/about')).rejects.toThrow('Rendering /about failed: boom');
    } finally {
      vi.doUnmock('@/pages/About');
    }
  });

  it('renders signed out, in the default theme, with no session probe', async () => {
    const html = await renderRoute('/');

    expect(html).toContain('Sign In');
    expect(html).toContain('aria-label="Switch to dark mode"');
  });
});

describe('entry-server pageMeta', () => {
  async function meta(path: string) {
    vi.resetModules();
    const { pageMeta } = await import('@/entry-server');
    return pageMeta(path);
  }

  it.each([
    ['/', 'BeCoMe - Best Compromise Mean', 'For panels that must settle on one number'],
    ['/about', 'About the Method - BeCoMe', 'Best Compromise Mean: a scientific method'],
    ['/terms', 'Terms of use - BeCoMe', 'The rules for using BeCoMe, in plain words.'],
    ['/case-study/budget', 'Case Study: COVID-19 Budget Support - BeCoMe', 'Budget allocation for pandemic response measures'],
  ])('gives %s its title and description', async (path, title, description) => {
    const result = await meta(path);

    expect(result.title).toBe(title);
    expect(result.description).toContain(description);
  });

  it('resolves every key of every public route to text', async () => {
    vi.resetModules();
    const { default: i18n } = await import('@/i18n');
    for (const route of publicRouteMeta) {
      const keys = [route.titleKey, route.descriptionKey, ...(route.titleNameKey ? [route.titleNameKey] : [])];
      for (const key of keys) {
        expect(i18n.exists(key, { lng: 'en' }), `${route.path}: ${key}`).toBe(true);
      }
      expect((await meta(route.path)).description.length, route.path).toBeGreaterThan(20);
    }
  });

  it('is in English whatever language the build machine reports', async () => {
    vi.stubGlobal('navigator', { language: 'cs-CZ', languages: ['cs-CZ', 'cs'] });

    expect((await meta('/about')).title).toBe('About the Method - BeCoMe');
  });

  it('refuses a path that is not a public route', async () => {
    await expect(meta('/projects')).rejects.toThrow('No page metadata for /projects');
  });
});

describe('entry-server 404 page', () => {
  it('renders the not-found screen at notFoundPath, which no route matches', async () => {
    vi.resetModules();
    const { render, notFoundPath, publicRoutes: listed } = await import('@/entry-server');

    expect(listed).not.toContain(notFoundPath);
    expect(heading(await render(notFoundPath))).toBe('404');
  });

  it('gives it the title and description NotFound shows, in English', async () => {
    vi.resetModules();
    vi.stubGlobal('navigator', { language: 'cs-CZ', languages: ['cs-CZ', 'cs'] });
    const { notFoundMeta } = await import('@/entry-server');

    expect(notFoundMeta()).toEqual({
      title: 'Page Not Found - BeCoMe',
      description: 'The requested page could not be found.',
    });
  });
});
