import { describe, it, expect } from 'vitest';
import { render, screen } from '@tests/utils';
import { OpinionLandscape } from '@/components/project';
import { createProjectWithRole, createOpinion, createCalculationResult } from '@tests/factories/project';

describe('OpinionLandscape - Best compromise marker', () => {
  it('shows the best compromise centroid and max error in the marker label', () => {
    const project = createProjectWithRole({ scale_min: 0, scale_max: 100 });
    const result = createCalculationResult({
      best_compromise: { lower: 35, peak: 52, upper: 68, centroid: 51.67 },
      max_error: 12.5,
    });
    const opinions = [createOpinion()];

    render(<OpinionLandscape result={result} project={project} opinions={opinions} />);

    const label = screen.getByTestId('landscape-best-label');
    expect(label.textContent).toContain('51.67');
    expect(label.textContent).toContain('12.50');
  });

  it('still renders the best compromise marker when there are no opinions', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();

    render(<OpinionLandscape result={result} project={project} opinions={[]} />);

    expect(screen.getByTestId('landscape-best-marker')).toBeInTheDocument();
  });
});

describe('OpinionLandscape - Expert dots', () => {
  it('renders one dot per expert opinion', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();
    const opinions = [createOpinion(), createOpinion(), createOpinion()];

    render(<OpinionLandscape result={result} project={project} opinions={opinions} />);

    expect(screen.getAllByTestId('opinion-dot')).toHaveLength(3);
  });

  it('renders a separate dot for each opinion even when centroids coincide', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();
    const opinions = [
      createOpinion({ centroid: 50 }),
      createOpinion({ centroid: 50 }),
    ];

    render(<OpinionLandscape result={result} project={project} opinions={opinions} />);

    const dots = screen.getAllByTestId('opinion-dot');
    expect(dots).toHaveLength(2);
    expect(dots[0].getAttribute('cx')).toBe(dots[1].getAttribute('cx'));
  });

  it('renders no dots when there are no opinions', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();

    render(<OpinionLandscape result={result} project={project} opinions={[]} />);

    expect(screen.queryAllByTestId('opinion-dot')).toHaveLength(0);
  });
});

describe('OpinionLandscape - Axis', () => {
  it('renders the scale min and max end labels', () => {
    const project = createProjectWithRole({ scale_min: 0, scale_max: 100 });
    const result = createCalculationResult();
    const opinions = [createOpinion()];

    const { container } = render(<OpinionLandscape result={result} project={project} opinions={opinions} />);

    const texts = Array.from(container.querySelectorAll('text')).map((el) => el.textContent);
    expect(texts).toContain('0');
    expect(texts).toContain('100');
  });
});

describe('OpinionLandscape - Accessibility', () => {
  it('exposes an accessible image role with a title and a description', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();
    const opinions = [createOpinion(), createOpinion()];

    const { container } = render(<OpinionLandscape result={result} project={project} opinions={opinions} />);

    expect(screen.getByRole('img')).toBeInTheDocument();
    expect(container.querySelector('title')?.textContent).toBeTruthy();
    const desc = container.querySelector('desc');
    expect(desc?.textContent).toContain(String(opinions.length));
  });

  it('describes the empty state instead of a bogus spread when there are no opinions', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult({
      best_compromise: { lower: 35, peak: 52, upper: 68, centroid: 51.67 },
    });

    const { container } = render(<OpinionLandscape result={result} project={project} opinions={[]} />);

    const desc = container.querySelector('desc');
    expect(desc?.textContent).toMatch(/no expert opinions/i);
    expect(desc?.textContent).toContain('51.67');
  });
});

describe('OpinionLandscape - Legend', () => {
  it('renders the expert, mean, median, and best legend labels', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();
    const opinions = [createOpinion()];

    render(<OpinionLandscape result={result} project={project} opinions={opinions} />);

    expect(screen.getByText('Expert')).toBeInTheDocument();
    expect(screen.getByText('Mean')).toBeInTheDocument();
    expect(screen.getByText('Median')).toBeInTheDocument();
    expect(screen.getByText('Best')).toBeInTheDocument();
  });
});
