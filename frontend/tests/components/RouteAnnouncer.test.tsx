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
