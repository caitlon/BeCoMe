import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { RouteAnnouncer } from '@/components/RouteAnnouncer';

// Shared navigate function, set by NavigateHelper inside MemoryRouter
let navigateFn: (path: string) => void;

function NavigateHelper() {
  const navigate = useNavigate();
  navigateFn = navigate;
  return null;
}

// Helper to render with router at a given path
function renderAnnouncer(initialPath = '/') {
  return render(
    <MemoryRouter
      initialEntries={[initialPath]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <RouteAnnouncer />
    </MemoryRouter>
  );
}

// Helper to render with router + NavigateHelper (for route change tests)
function renderWithNavigate(initialPath = '/') {
  return render(
    <MemoryRouter
      initialEntries={[initialPath]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <RouteAnnouncer />
      <NavigateHelper />
    </MemoryRouter>
  );
}

describe('RouteAnnouncer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    // Create main-content element for focus tests
    const main = document.createElement('main');
    main.id = 'main-content';
    document.body.appendChild(main);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.title = '';
    const main = document.getElementById('main-content');
    if (main) main.remove();
  });

  it('renders with aria-live="polite" and aria-atomic="true"', () => {
    renderAnnouncer();

    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveAttribute('aria-atomic', 'true');
  });

  it('has sr-only class', () => {
    renderAnnouncer();

    const region = screen.getByRole('status');
    expect(region).toHaveClass('sr-only');
  });

  it('announces nothing on initial render', () => {
    renderAnnouncer();

    act(() => { vi.advanceTimersByTime(200); });

    const region = screen.getByRole('status');
    expect(region).toHaveTextContent('');
  });

  it('announces document.title after route change', () => {
    document.title = 'Projects — BeCoMe';

    renderWithNavigate();

    act(() => { navigateFn('/projects'); });
    act(() => { vi.advanceTimersByTime(150); });

    expect(screen.getByRole('status')).toHaveTextContent('Projects — BeCoMe');
  });

  it('calls window.scrollTo(0, 0) on route change', () => {
    renderWithNavigate();

    act(() => { navigateFn('/about'); });

    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);
  });

  it('focuses main-content element and sets tabindex="-1"', () => {
    const main = document.getElementById('main-content')!;
    const focusSpy = vi.spyOn(main, 'focus');

    renderWithNavigate();

    act(() => { navigateFn('/projects'); });

    expect(main).toHaveAttribute('tabindex', '-1');
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
  });

  it('retries focusing main-content via rAF when element is missing', () => {
    // Remove main-content so retry logic kicks in
    const main = document.getElementById('main-content')!;
    main.remove();

    const rAFSpy = vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation((cb) => {
      // Don't actually call callback to avoid infinite loop
      return 1;
    });
    const cancelSpy = vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation(() => {});

    renderWithNavigate();

    act(() => { navigateFn('/projects'); });

    // focusMain should have called requestAnimationFrame since main-content is missing
    expect(rAFSpy).toHaveBeenCalled();

    rAFSpy.mockRestore();
    cancelSpy.mockRestore();
  });

  it('cancels rAF on cleanup when main-content is missing', () => {
    // Remove main-content
    const main = document.getElementById('main-content')!;
    main.remove();

    const cancelSpy = vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation(() => {});
    vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation(() => 42);

    const { unmount } = renderWithNavigate();

    act(() => { navigateFn('/about'); });

    unmount();

    expect(cancelSpy).toHaveBeenCalledWith(42);

    cancelSpy.mockRestore();
  });

  it('does not re-announce when pathname stays the same', () => {
    document.title = 'Home — BeCoMe';
    renderWithNavigate();

    // Let initial announcement fire
    act(() => { vi.advanceTimersByTime(150); });
    expect(screen.getByRole('status')).toHaveTextContent('Home — BeCoMe');

    // Change title, then navigate to same path with different search params
    document.title = 'Should Not Appear';
    act(() => { navigateFn('/?query=test'); });
    act(() => { vi.advanceTimersByTime(200); });

    // Still shows old announcement — no new one triggered
    expect(screen.getByRole('status')).toHaveTextContent('Home — BeCoMe');
  });
});
