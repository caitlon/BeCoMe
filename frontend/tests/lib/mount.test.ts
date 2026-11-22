import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isHydrating, setHydrating } from '@/lib/hydration';

const mocks = vi.hoisted(() => ({
  hydrateRoot: vi.fn(),
  render: vi.fn(),
  createRoot: vi.fn(),
  reactErrorHandler: vi.fn(),
  logError: vi.fn(),
}));

vi.mock('react-dom/client', () => ({
  hydrateRoot: mocks.hydrateRoot,
  createRoot: mocks.createRoot,
}));
vi.mock('@sentry/react', () => ({ reactErrorHandler: mocks.reactErrorHandler }));
vi.mock('@/lib/logger', () => ({ logger: { error: mocks.logError } }));

import { mountApp } from '@/lib/mount';

function rootWith(html: string, route?: string): HTMLElement {
  const root = document.createElement('div');
  root.innerHTML = html;
  if (route !== undefined) root.setAttribute('data-route', route);
  return root;
}

describe('mountApp', () => {
  const tree = 'the tree';
  const handler = vi.fn();

  beforeEach(() => {
    setHydrating(false);
    globalThis.history.pushState({}, '', '/about');
    mocks.logError.mockReset();
    mocks.hydrateRoot.mockReset();
    mocks.render.mockReset();
    mocks.createRoot.mockReset().mockReturnValue({ render: mocks.render });
    mocks.reactErrorHandler.mockReset().mockReturnValue(handler);
  });

  afterEach(() => setHydrating(false));

  it('sets the hydrating flag before it hydrates prerendered English content', () => {
    let hydratingWhenCalled: boolean | undefined;
    mocks.hydrateRoot.mockImplementation(() => {
      hydratingWhenCalled = isHydrating();
    });
    const root = rootWith('<main>About</main>', '/about');

    mountApp(root, tree, 'en');

    expect(hydratingWhenCalled).toBe(true);
    expect(mocks.hydrateRoot).toHaveBeenCalledWith(root, tree, { onRecoverableError: handler });
    expect(mocks.createRoot).not.toHaveBeenCalled();
  });

  it('gives Sentry a callback, so a recoverable hydration error counts as handled', () => {
    mountApp(rootWith('<main>About</main>', '/about'), tree, 'en');

    expect(mocks.reactErrorHandler).toHaveBeenCalledWith(expect.any(Function));
  });

  it('logs a recoverable hydration error through the logger', () => {
    mountApp(rootWith('<main>About</main>', '/about'), tree, 'en');
    const callback = mocks.reactErrorHandler.mock.calls[0][0] as (error: unknown) => void;

    callback(new Error('mismatch'));
    callback('not an error object');

    expect(mocks.logError).toHaveBeenNthCalledWith(1, 'Recoverable hydration error', { error: 'mismatch' });
    expect(mocks.logError).toHaveBeenNthCalledWith(2, 'Recoverable hydration error', {
      error: 'not an error object',
    });
  });

  it('renders a fresh tree for a Czech visitor and leaves the flag off', () => {
    mountApp(rootWith('<main>About</main>', '/about'), tree, 'cs');

    expect(mocks.createRoot).toHaveBeenCalled();
    expect(mocks.render).toHaveBeenCalledWith(tree);
    expect(mocks.hydrateRoot).not.toHaveBeenCalled();
    expect(isHydrating()).toBe(false);
  });

  it('renders a fresh tree when the prerendered page is for another route', () => {
    globalThis.history.pushState({}, '', '/case-study/unknown');

    mountApp(rootWith('<main>About</main>', '/about'), tree, 'en');

    expect(mocks.render).toHaveBeenCalledWith(tree);
    expect(mocks.hydrateRoot).not.toHaveBeenCalled();
    expect(isHydrating()).toBe(false);
  });

  it('renders a fresh tree over the 404 page, which carries no route', () => {
    mountApp(rootWith('<main>404</main>'), tree, 'en');

    expect(mocks.render).toHaveBeenCalledWith(tree);
    expect(mocks.hydrateRoot).not.toHaveBeenCalled();
  });

  it('renders a fresh tree into an empty root and leaves the flag off', () => {
    mountApp(rootWith(''), tree, 'en');

    expect(mocks.render).toHaveBeenCalledWith(tree);
    expect(mocks.hydrateRoot).not.toHaveBeenCalled();
    expect(isHydrating()).toBe(false);
  });
});
