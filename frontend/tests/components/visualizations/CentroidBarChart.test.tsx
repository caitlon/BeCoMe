import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { CentroidBarChart } from '@/components/visualizations/CentroidBarChart';
import { createOpinion, createCalculationResult } from '@tests/factories/project';

// Mock recharts to avoid SVG rendering in happy-dom
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    ScatterChart: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div data-testid="scatter-chart" data-accessibility-layer={props.accessibilityLayer}>
        {children}
      </div>
    ),
    Scatter: (props: Record<string, unknown>) => (
      <div data-testid="scatter" data-animation-active={String(props.isAnimationActive)} />
    ),
    XAxis: () => <div data-testid="x-axis" />,
    YAxis: () => <div data-testid="y-axis" />,
    ReferenceLine: ({ x, stroke }: { x?: number; stroke?: string }) => (
      <div data-testid="reference-line" data-x={x} data-stroke={stroke} />
    ),
    Tooltip: () => null,
  };
});

const opinions = [
  createOpinion({ user_first_name: 'Anna', user_last_name: 'Lee', centroid: 60, lower_bound: 40, peak: 60, upper_bound: 80 }),
  createOpinion({ user_first_name: 'Bob', user_last_name: 'Smith', centroid: 30, lower_bound: 10, peak: 30, upper_bound: 50 }),
  createOpinion({ user_first_name: 'Clara', user_last_name: null, centroid: 45, lower_bound: 25, peak: 45, upper_bound: 65 }),
];

const result = createCalculationResult();

describe('CentroidBarChart', () => {
  it('renders as a figure with aria-label', () => {
    render(<CentroidBarChart opinions={opinions} result={result} />);

    const figure = screen.getByRole('figure');
    expect(figure).toHaveAttribute('aria-label');
  });

  it('has sr-only summary with expert count and centroid range', () => {
    const { container } = render(<CentroidBarChart opinions={opinions} result={result} />);

    const srOnly = container.querySelector('.sr-only');
    expect(srOnly).toBeInTheDocument();
    expect(srOnly?.textContent).toContain('3');
    expect(srOnly?.textContent).toContain('30');
    expect(srOnly?.textContent).toContain('60');
  });

  it('renders three reference lines for aggregates', () => {
    render(<CentroidBarChart opinions={opinions} result={result} />);

    const referenceLines = screen.getAllByTestId('reference-line');
    expect(referenceLines).toHaveLength(3);

    // Each reference line should have an x value (centroid of an aggregate)
    referenceLines.forEach((line) => {
      expect(line).toHaveAttribute('data-x');
    });
  });

  it('renders legend with aria-hidden and aggregate values', () => {
    const { container } = render(<CentroidBarChart opinions={opinions} result={result} />);

    const figure = container.querySelector('figure');
    const legend = figure?.querySelector('[aria-hidden="true"]');
    expect(legend).toBeInTheDocument();
    expect(legend?.textContent).toContain('Mean');
    expect(legend?.textContent).toContain('Median');
    expect(legend?.textContent).toContain('Centroid');
    // Legend should show numeric values of aggregates
    expect(legend?.textContent).toContain(result.arithmetic_mean.centroid.toFixed(1));
  });

  it('enables accessibilityLayer on ScatterChart', () => {
    render(<CentroidBarChart opinions={opinions} result={result} />);

    const scatterChart = screen.getByTestId('scatter-chart');
    expect(scatterChart).toHaveAttribute('data-accessibility-layer', 'true');
  });

  it('disables animation when prefers-reduced-motion is set', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    render(<CentroidBarChart opinions={opinions} result={result} />);

    const scatter = screen.getByTestId('scatter');
    expect(scatter).toHaveAttribute('data-animation-active', 'false');
  });
});
