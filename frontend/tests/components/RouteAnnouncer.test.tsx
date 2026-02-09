import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RouteAnnouncer } from '@/components/RouteAnnouncer';

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
    // Use a NavigateHelper to trigger route change inside the router
    let navigateFn: (path: string) => void;

    function NavigateHelper() {
      const { useNavigate } = require('react-router-dom');
      const navigate = useNavigate();
      navigateFn = navigate;
      return null;
    }

    document.title = 'Projects — BeCoMe';

    render(
      <MemoryRouter
        initialEntries={['/']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <RouteAnnouncer />
        <NavigateHelper />
      </MemoryRouter>
    );

    act(() => { navigateFn!('/projects'); });
    act(() => { vi.advanceTimersByTime(150); });

    expect(screen.getByRole('status')).toHaveTextContent('Projects — BeCoMe');
  });

  it('calls window.scrollTo(0, 0) on route change', () => {
    let navigateFn: (path: string) => void;

    function NavigateHelper() {
      const { useNavigate } = require('react-router-dom');
      const navigate = useNavigate();
      navigateFn = navigate;
      return null;
    }

    render(
      <MemoryRouter
        initialEntries={['/']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <RouteAnnouncer />
        <NavigateHelper />
      </MemoryRouter>
    );

    act(() => { navigateFn!('/about'); });

    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);
  });

  it('focuses main-content element and sets tabindex="-1"', () => {
    let navigateFn: (path: string) => void;

    function NavigateHelper() {
      const { useNavigate } = require('react-router-dom');
      const navigate = useNavigate();
      navigateFn = navigate;
      return null;
    }

    const main = document.getElementById('main-content')!;
    const focusSpy = vi.spyOn(main, 'focus');

    render(
      <MemoryRouter
        initialEntries={['/']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <RouteAnnouncer />
        <NavigateHelper />
      </MemoryRouter>
    );

    act(() => { navigateFn!('/projects'); });

    expect(main).toHaveAttribute('tabindex', '-1');
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
  });

  it('does not announce when pathname stays the same', () => {
    let navigateFn: (path: string) => void;

    function NavigateHelper() {
      const { useNavigate } = require('react-router-dom');
      const navigate = useNavigate();
      navigateFn = navigate;
      return null;
    }

    render(
      <MemoryRouter
        initialEntries={['/']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <RouteAnnouncer />
        <NavigateHelper />
      </MemoryRouter>
    );

    // Navigate to same path with different search params
    act(() => { navigateFn!('/?query=test'); });
    act(() => { vi.advanceTimersByTime(200); });

    expect(screen.getByRole('status')).toHaveTextContent('');
  });
});
