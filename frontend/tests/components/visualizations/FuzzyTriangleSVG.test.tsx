import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, act, fireEvent } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { FuzzyTriangleSVG } from '@/components/visualizations/FuzzyTriangleSVG';
import i18n from '@/i18n';

vi.mock('framer-motion', () => framerMotionMock);

// Mock matchMedia
let prefersReducedMotion = false;

beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? prefersReducedMotion : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => {
  vi.useRealTimers();
  prefersReducedMotion = false;
});

describe('FuzzyTriangleSVG', () => {
  it('SVG has aria-labelledby for accessibility', () => {
    render(<FuzzyTriangleSVG />);

    expect(screen.getByRole('img', { name: /fuzzy triangular/i })).toBeInTheDocument();
  });

  it('has <title> and <desc> elements with correct IDs', () => {
    const { container } = render(<FuzzyTriangleSVG />);

    const title = container.querySelector('#fuzzy-triangle-title');
    const desc = container.querySelector('#fuzzy-triangle-desc');
    expect(title).toBeInTheDocument();
    expect(title?.tagName.toLowerCase()).toBe('title');
    expect(desc).toBeInTheDocument();
    expect(desc?.tagName.toLowerCase()).toBe('desc');
  });

  it('renders axis labels', () => {
    render(<FuzzyTriangleSVG />);

    // Use exact text from i18n (en: Lower, Peak, Upper)
    expect(screen.getByText('Lower')).toBeInTheDocument();
    expect(screen.getByText('Peak')).toBeInTheDocument();
    expect(screen.getByText('Upper')).toBeInTheDocument();
  });

  it('renders three dashed triangle outlines', () => {
    const { container } = render(<FuzzyTriangleSVG />);

    // 3 static dashed polygons + 1 animated motion.polygon = expect at least 3 with strokeDasharray
    const dashedPolygons = container.querySelectorAll('polygon[stroke-dasharray]');
    expect(dashedPolygons.length).toBe(3);
  });

  it('skips animation interval when prefers-reduced-motion is reduce', () => {
    prefersReducedMotion = true;
    const { container } = render(<FuzzyTriangleSVG />);

    const animatedPolygon = container.querySelector('polygon:not([stroke-dasharray])');
    const initialPoints = animatedPolygon?.getAttribute('points');

    // Five seconds is two ticks of the 2s interval, deliberately not a whole
    // number of trips round the three forms: a wrap would land back on the
    // starting points and the assertion below could not fail.
    act(() => { vi.advanceTimersByTime(5000); });

    const updatedPoints = animatedPolygon?.getAttribute('points');
    expect(updatedPoints).toBe(initialPoints);
  });

  it('cycles through forms when motion is allowed', () => {
    prefersReducedMotion = false;
    const { container } = render(<FuzzyTriangleSVG />);

    // The animated polygon starts with first form's points
    const animatedPolygon = container.querySelector('polygon:not([stroke-dasharray])');
    const initialPoints = animatedPolygon?.getAttribute('points');

    // Advance past the interval (2 seconds) wrapped in act for state update
    act(() => { vi.advanceTimersByTime(2100); });

    // Points should have changed to second form
    const updatedPoints = animatedPolygon?.getAttribute('points');
    expect(updatedPoints).not.toBe(initialPoints);
  });

  it('does not cycle when matchMedia is not a function', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: undefined,
    });

    const { container } = render(<FuzzyTriangleSVG />);
    const animatedPolygon = container.querySelector('polygon:not([stroke-dasharray])');
    const initialPoints = animatedPolygon?.getAttribute('points');

    act(() => { vi.advanceTimersByTime(5000); });

    expect(animatedPolygon?.getAttribute('points')).toBe(initialPoints);
  });

  describe('pause control', () => {
    const animatedPoints = (container: HTMLElement) =>
      container.querySelector('polygon:not([stroke-dasharray])')?.getAttribute('points');

    it('offers a button that names the action it will take', () => {
      render(<FuzzyTriangleSVG />);

      const pause = screen.getByRole('button', { name: 'Pause animation' });
      expect(pause).not.toHaveAttribute('aria-pressed');

      fireEvent.click(pause);

      expect(screen.getByRole('button', { name: 'Play animation' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Pause animation' })).not.toBeInTheDocument();
    });

    it('stops the cycle while paused and resumes it on the second press', () => {
      const { container } = render(<FuzzyTriangleSVG />);
      const initialPoints = animatedPoints(container);

      fireEvent.click(screen.getByRole('button', { name: 'Pause animation' }));
      // Five seconds is two ticks of the 2s interval, so a live cycle would move.
      act(() => { vi.advanceTimersByTime(5000); });
      expect(animatedPoints(container)).toBe(initialPoints);

      fireEvent.click(screen.getByRole('button', { name: 'Play animation' }));
      act(() => { vi.advanceTimersByTime(2100); });
      expect(animatedPoints(container)).not.toBe(initialPoints);
    });

    it('starts paused when the visitor prefers reduced motion', () => {
      prefersReducedMotion = true;
      const { container } = render(<FuzzyTriangleSVG />);
      const initialPoints = animatedPoints(container);

      expect(screen.getByRole('button', { name: 'Play animation' })).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: 'Play animation' }));
      act(() => { vi.advanceTimersByTime(2100); });
      expect(animatedPoints(container)).not.toBe(initialPoints);
    });

    it('names the action in Czech', async () => {
      await i18n.changeLanguage('cs');
      try {
        const { unmount } = render(<FuzzyTriangleSVG />);

        fireEvent.click(screen.getByRole('button', { name: 'Pozastavit animaci' }));
        expect(screen.getByRole('button', { name: 'Spustit animaci' })).toBeInTheDocument();

        unmount();
      } finally {
        await i18n.changeLanguage('en');
      }
    });
  });
});
