import { describe, it, expect } from 'vitest';
import { render } from '@tests/utils';
import { TriangleVisualization } from '@/components/project';
import { createProjectWithRole, createOpinion, createCalculationResult } from '@tests/factories/project';

describe('TriangleVisualization - Scale Labels', () => {
  it('renders the scale min and max labels with the unit appended to the max', () => {
    const project = createProjectWithRole({ scale_min: 0, scale_max: 100, scale_unit: '%' });
    const result = createCalculationResult();

    const { container } = render(
      <TriangleVisualization result={result} project={project} showIndividual={false} opinions={[]} />
    );

    const texts = Array.from(container.querySelectorAll('text')).map((el) => el.textContent);
    expect(texts).toContain('0');
    expect(texts).toContain('100 %');
  });

  it('omits the unit suffix when the scale has no unit', () => {
    const project = createProjectWithRole({ scale_min: 0, scale_max: 100, scale_unit: '' });
    const result = createCalculationResult();

    const { container } = render(
      <TriangleVisualization result={result} project={project} showIndividual={false} opinions={[]} />
    );

    const texts = Array.from(container.querySelectorAll('text')).map((el) => el.textContent);
    expect(texts).toContain('100');
  });

  it('renders the accessible chart title', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();

    const { container } = render(
      <TriangleVisualization result={result} project={project} showIndividual={false} opinions={[]} />
    );

    expect(container.querySelector('title')).not.toBeNull();
  });
});

describe('TriangleVisualization - Individual Opinions', () => {
  it('does not render individual opinion polygons when showIndividual is false', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();
    const opinions = [createOpinion(), createOpinion()];

    const { container } = render(
      <TriangleVisualization result={result} project={project} showIndividual={false} opinions={opinions} />
    );

    // 3 fixed polygons: arithmetic mean, median, best compromise
    expect(container.querySelectorAll('polygon')).toHaveLength(3);
  });

  it('renders one extra polygon per opinion when showIndividual is true', () => {
    const project = createProjectWithRole();
    const result = createCalculationResult();
    const opinions = [createOpinion(), createOpinion()];

    const { container } = render(
      <TriangleVisualization result={result} project={project} showIndividual opinions={opinions} />
    );

    // 3 fixed polygons + 1 per individual opinion
    expect(container.querySelectorAll('polygon')).toHaveLength(3 + opinions.length);
  });
});
