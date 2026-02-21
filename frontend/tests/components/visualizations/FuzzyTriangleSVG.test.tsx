import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, act } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { FuzzyTriangleSVG } from '@/components/visualizations/FuzzyTriangleSVG';

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

    // After 6 seconds (2 full cycles), points should remain unchanged
    act(() => { vi.advanceTimersByTime(6000); });

    const updatedPoints = animatedPolygon?.getAttribute('points');
    expect(updatedPoints).toBe(initialPoints);
  });

  it('cycles through forms when motion is allowed', () => {
    prefersReducedMotion = false;
    const { container } = render(<FuzzyTriangleSVG />);

    // The animated polygon starts with first form's points
    const animatedPolygon = container.querySelector('polygon:not([stroke-dasharray])');
    const initialPoints = animatedPolygon?.getAttribute('points');

    // Advance past the interval (3 seconds) wrapped in act for state update
    act(() => { vi.advanceTimersByTime(3100); });

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

    act(() => { vi.advanceTimersByTime(6000); });

    expect(animatedPolygon?.getAttribute('points')).toBe(initialPoints);
  });
});
