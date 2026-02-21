import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { CentroidBarChart } from '@/components/visualizations/CentroidBarChart';
import { createOpinion, createCalculationResult, resetProjectCounters } from '@tests/factories/project';

const tooltipFlag = vi.hoisted(() => ({
  renderContent: false,
  tooltipPayload: null as Array<{ payload: Record<string, unknown> }> | null,
}));

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
    XAxis: ({ tickFormatter }: { tickFormatter?: (v: number) => string }) => (
      <div data-testid="x-axis">
        {tickFormatter && (
          <>
            <span data-testid="tick-integer">{tickFormatter(10)}</span>
            <span data-testid="tick-decimal">{tickFormatter(10.5)}</span>
          </>
        )}
      </div>
    ),
    YAxis: () => <div data-testid="y-axis" />,
    ReferenceLine: ({ x, stroke }: { x?: number; stroke?: string }) => (
      <div data-testid="reference-line" data-x={x} data-stroke={stroke} />
    ),
    Tooltip: ({ content }: { content?: React.ReactElement }) => {
      if (!tooltipFlag.renderContent || !content) return null;
      return (
        <div data-testid="tooltip-wrapper">
          {React.cloneElement(content, {
            active: true,
            payload: tooltipFlag.tooltipPayload,
          })}
        </div>
      );
    },
  };
});

const opinions = [
  createOpinion({ user_first_name: 'Anna', user_last_name: 'Lee', centroid: 60, lower_bound: 40, peak: 60, upper_bound: 80 }),
  createOpinion({ user_first_name: 'Bob', user_last_name: 'Smith', centroid: 30, lower_bound: 10, peak: 30, upper_bound: 50 }),
  createOpinion({ user_first_name: 'Clara', user_last_name: null, centroid: 45, lower_bound: 25, peak: 45, upper_bound: 65 }),
];

const result = createCalculationResult();

let originalMatchMedia: typeof globalThis.matchMedia;

beforeEach(() => {
  resetProjectCounters();
  originalMatchMedia = globalThis.matchMedia;
  tooltipFlag.renderContent = false;
});

afterEach(() => {
  Object.defineProperty(globalThis, 'matchMedia', {
    writable: true,
    value: originalMatchMedia,
  });
});

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
    expect(legend?.textContent).toContain(result.arithmetic_mean.centroid.toFixed(1));
  });

  it('enables accessibilityLayer on ScatterChart', () => {
    render(<CentroidBarChart opinions={opinions} result={result} />);

    const scatterChart = screen.getByTestId('scatter-chart');
    expect(scatterChart).toHaveAttribute('data-accessibility-layer', 'true');
  });

  it('disables animation when prefers-reduced-motion is set', () => {
    Object.defineProperty(globalThis, 'matchMedia', {
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

  it('enables animation when matchMedia is not available', () => {
    Object.defineProperty(globalThis, 'matchMedia', {
      writable: true,
      value: undefined,
    });

    render(<CentroidBarChart opinions={opinions} result={result} />);

    const scatter = screen.getByTestId('scatter');
    expect(scatter).toHaveAttribute('data-animation-active', 'true');
  });
});

describe('CentroidBarChart - tickFormatter', () => {
  it('formats integer values without decimals', () => {
    render(<CentroidBarChart opinions={opinions} result={result} />);

    const tickInteger = screen.getByTestId('tick-integer');
    expect(tickInteger.textContent).toBe('10');
  });

  it('formats decimal values to one decimal place', () => {
    render(<CentroidBarChart opinions={opinions} result={result} />);

    const tickDecimal = screen.getByTestId('tick-decimal');
    expect(tickDecimal.textContent).toBe('10.5');
  });
});

describe('CentroidBarChart - edge cases', () => {
  it('handles empty opinions array', () => {
    render(<CentroidBarChart opinions={[]} result={result} />);

    const figure = screen.getByRole('figure');
    expect(figure).toBeInTheDocument();

    const srOnly = figure.querySelector('.sr-only');
    expect(srOnly?.textContent).toContain('0');
  });

  it('handles equal centroids with padding fallback', () => {
    const sameOpinions = [
      createOpinion({ centroid: 50, lower_bound: 40, peak: 50, upper_bound: 60 }),
      createOpinion({ centroid: 50, lower_bound: 45, peak: 50, upper_bound: 55 }),
    ];

    render(<CentroidBarChart opinions={sameOpinions} result={result} />);

    const figure = screen.getByRole('figure');
    expect(figure).toBeInTheDocument();
  });

  it('trims full name when last name is null', () => {
    tooltipFlag.renderContent = true;
    tooltipFlag.tooltipPayload = [{
      payload: { x: 50, y: 1, centroid: 50, lower: 40, peak: 50, upper: 60, fullName: 'Solo', position: 'Expert' },
    }];
    const opWithNullLast = [
      createOpinion({ user_first_name: 'Solo', user_last_name: null, centroid: 50 }),
    ];

    render(<CentroidBarChart opinions={opWithNullLast} result={result} />);

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip.textContent).toContain('Solo');
  });
});

describe('CentroidBarChart - CustomTooltip', () => {
  beforeEach(() => {
    tooltipFlag.renderContent = true;
  });

  it('renders tooltip with expert name and fuzzy values', () => {
    tooltipFlag.tooltipPayload = [{
      payload: { x: 45, y: 1, centroid: 45, lower: 25, peak: 45, upper: 65, fullName: 'Clara', position: 'Expert' },
    }];

    render(<CentroidBarChart opinions={opinions} result={result} />);

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toBeInTheDocument();
    expect(tooltip.textContent).toContain('Clara');
    expect(tooltip.textContent).toContain('45.00');
  });

  it('renders tooltip with position when position is present', () => {
    tooltipFlag.tooltipPayload = [{
      payload: { x: 50, y: 1, centroid: 50, lower: 40, peak: 50, upper: 60, fullName: 'Jane Doe', position: 'Senior Analyst' },
    }];

    render(<CentroidBarChart opinions={opinions} result={result} />);

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip.textContent).toContain('Senior Analyst');
  });

  it('omits position when position is empty string', () => {
    tooltipFlag.tooltipPayload = [{
      payload: { x: 50, y: 1, centroid: 50, lower: 40, peak: 50, upper: 60, fullName: 'Jane', position: '' },
    }];

    render(<CentroidBarChart opinions={opinions} result={result} />);

    const tooltip = screen.getByRole('tooltip');
    // Name should be there, but no extra empty div for position
    expect(tooltip.textContent).toContain('Jane');
    // Only 3 child divs: name, fuzzy values container, centroid value
    const directChildren = tooltip.querySelectorAll(':scope > div');
    expect(directChildren).toHaveLength(2);
  });

  it('returns null when payload is empty', () => {
    tooltipFlag.tooltipPayload = [];

    render(<CentroidBarChart opinions={opinions} result={result} />);

    const tooltipWrapper = screen.getByTestId('tooltip-wrapper');
    expect(tooltipWrapper.querySelector('[role="tooltip"]')).toBeNull();
  });
});
