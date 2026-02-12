import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { StepViewResults } from '@/components/onboarding/StepViewResults';

vi.mock('framer-motion', () => framerMotionMock);

describe('StepViewResults', () => {
  it('renders heading', () => {
    render(<StepViewResults />);

    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
  });

  it('renders description', () => {
    const { container } = render(<StepViewResults />);

    const description = container.querySelector('.text-muted-foreground.text-center.max-w-md');
    expect(description).toBeInTheDocument();
  });

  it('displays Best Compromise value 54.3', () => {
    render(<StepViewResults />);

    expect(screen.getByText('54.3')).toBeInTheDocument();
  });

  it('displays fuzzy triple (42.1 | 54.3 | 68.7)', () => {
    render(<StepViewResults />);

    expect(screen.getByText('(42.1 | 54.3 | 68.7)')).toBeInTheDocument();
  });

  it('displays Max Error value 8.2', () => {
    render(<StepViewResults />);

    expect(screen.getByText('8.2')).toBeInTheDocument();
  });

  it('displays Experts count 12', () => {
    render(<StepViewResults />);

    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('renders hint text', () => {
    const { container } = render(<StepViewResults />);

    const hint = container.querySelector('.text-xs.text-muted-foreground.italic');
    expect(hint).toBeInTheDocument();
  });
});
