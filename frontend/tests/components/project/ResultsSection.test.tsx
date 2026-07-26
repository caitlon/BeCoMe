import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import { ResultsSection } from '@/components/project';
import {
  createProjectWithRole,
  createOpinion,
  createCalculationResult,
} from '@tests/factories/project';

vi.mock('framer-motion', () => framerMotionMock);

const setup = () => {
  const project = createProjectWithRole({ id: 'project-1', name: 'Test Project' });
  const opinions = [createOpinion({ user_id: 'other' })];
  return { project, opinions };
};

describe('ResultsSection - Empty State', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows "no results" message when no opinions', () => {
    const { project } = setup();

    render(<ResultsSection result={null} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={[]} />);

    expect(screen.getByText(/results will appear once experts submit/i)).toBeInTheDocument();
  });
});

describe('ResultsSection - Results Display', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays calculation results when available', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Best Compromise')).toBeInTheDocument();
  });

  it('shows agreement badge with results', () => {
    // max_error=12.5, scale 0-100, errorPercent=12.5% → "High agreement"
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 12.5 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('High agreement')).toBeInTheDocument();
  });

  it('shows moderate agreement for medium error', () => {
    // max_error=30, scale 0-100, errorPercent=30% → "Moderate agreement"
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 30 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Moderate agreement')).toBeInTheDocument();
  });

  it('shows low agreement for high error', () => {
    // max_error=50, scale 0-100, errorPercent=50% → "Low agreement"
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 50 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Low agreement')).toBeInTheDocument();
  });

  it('toggles individual opinions visibility via checkbox', async () => {
    const user = userEvent.setup();
    const { project, opinions } = setup();
    const result = createCalculationResult();
    const setShowIndividual = vi.fn();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={setShowIndividual} opinions={opinions} />);

    // The checkbox lives on the Triangle tab, which is no longer the default.
    await user.click(screen.getByRole('tab', { name: /triangle/i }));

    const checkbox = screen.getByRole('checkbox', { name: /individual/i });
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);
    expect(setShowIndividual).toHaveBeenCalledWith(true);
  });

  it('renders visualization tabs (Landscape, Triangle, and Centroid)', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByRole('tab', { name: /landscape/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /triangle/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /centroid/i })).toBeInTheDocument();
  });

  it('defaults the visualization to the Landscape tab', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByRole('tab', { name: /landscape/i })).toHaveAttribute('data-state', 'active');
    // Landscape-only content (its "Expert" legend entry) is visible without clicking anything.
    expect(screen.getByText('Expert')).toBeInTheDocument();
  });

  it('labels the show-individual checkbox with a generated id, not a hardcoded one', async () => {
    const user = userEvent.setup();
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);
    await user.click(screen.getByRole('tab', { name: /triangle/i }));

    // The label/checkbox association still works ...
    const checkbox = screen.getByRole('checkbox', { name: /individual/i });
    // ... but the collision-prone hardcoded id is gone (it duplicated when the
    // section was mounted for both the desktop and mobile layouts at once).
    expect(document.querySelector('#showIndividual')).toBeNull();
    expect(checkbox.id).not.toBe('showIndividual');
    expect(checkbox.id).not.toBe('');
  });

  it('keeps the arithmetic mean and median values on a single non-wrapping line', async () => {
    const user = userEvent.setup();
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    // Mean/median live behind the collapsed-by-default "Supporting calculations" trigger.
    await user.click(screen.getByRole('button', { name: /supporting calculations/i }));

    // Factory values: arithmetic_mean 32 | 50 | 70, median 38 | 54 | 66.
    const meanValue = await screen.findByText('32.00 | 50.00 | 70.00');
    const medianValue = screen.getByText('38.00 | 54.00 | 66.00');
    for (const el of [meanValue, medianValue]) {
      expect(el).toHaveClass('whitespace-nowrap');
      expect(el).toHaveClass('tabular-nums');
    }
  });

  it('labels the best compromise card with a result badge', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Best Compromise')).toBeInTheDocument();
    expect(screen.getByText('Result')).toBeInTheDocument();
  });
});

describe('ResultsSection - Supporting Calculations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('collapses the mean/median cards by default', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    const trigger = screen.getByRole('button', { name: /supporting calculations/i });
    expect(trigger).toHaveAttribute('data-state', 'closed');
    expect(screen.queryByText('32.00 | 50.00 | 70.00')).not.toBeInTheDocument();
  });

  it('reveals the mean/median cards once the trigger is expanded', async () => {
    const user = userEvent.setup();
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    const trigger = screen.getByRole('button', { name: /supporting calculations/i });
    await user.click(trigger);

    expect(trigger).toHaveAttribute('data-state', 'open');
    expect(await screen.findByText('32.00 | 50.00 | 70.00')).toBeInTheDocument();
    expect(screen.getByText('38.00 | 54.00 | 66.00')).toBeInTheDocument();
  });
});

describe('ResultsSection - Best Compromise Hero', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('leads with the centroid and error margin as the hero value', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    // Factory defaults: best_compromise centroid 51.67, max_error 12.5.
    expect(screen.getByText('51.67')).toBeInTheDocument();
    expect(screen.getByText('± 12.50')).toBeInTheDocument();
  });

  it('shows the agreement level as a confidence pill next to the hero value', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 12.5 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('High Confidence')).toBeInTheDocument();
  });

  it('shows a moderate confidence pill for medium error', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 30 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Moderate Confidence')).toBeInTheDocument();
  });

  it('shows a low confidence pill for high error', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 50 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Low Confidence')).toBeInTheDocument();
  });

  it('keeps lower/peak/upper as a secondary range row below the hero value', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    // Factory defaults: best_compromise lower 35, peak 52, upper 68.
    expect(screen.getByText('35.00')).toBeInTheDocument();
    expect(screen.getByText('52.00')).toBeInTheDocument();
    expect(screen.getByText('68.00')).toBeInTheDocument();
  });
});

describe('ResultsSection - Confidence Card', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('relabels the heading from Max Error to Confidence, keeping the Delta_max suffix', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Confidence')).toBeInTheDocument();
    expect(screen.getByText('(Δmax)')).toBeInTheDocument();
    expect(screen.queryByText(/Max Error/)).not.toBeInTheDocument();
  });

  it('explains what the confidence score means', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(
      screen.getByText(/tighter agreement means a more precise compromise/i)
    ).toBeInTheDocument();
  });

  it('keeps the Delta_max number visible', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 12.5 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('12.50')).toBeInTheDocument();
  });

  it('keeps the agreement badge and experts count unchanged', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 12.5, num_experts: 5 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('High agreement')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });
});
