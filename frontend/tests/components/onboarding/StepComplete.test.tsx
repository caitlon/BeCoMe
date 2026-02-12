import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { StepComplete } from '@/components/onboarding/StepComplete';

vi.mock('framer-motion', () => framerMotionMock);

describe('StepComplete', () => {
  it('renders completion title', () => {
    render(<StepComplete />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('renders description text', () => {
    render(<StepComplete />);

    expect(screen.getByText(/basics|základy/i)).toBeInTheDocument();
  });

  it('renders link to projects page', () => {
    render(<StepComplete />);

    const projectsLink = screen.getByRole('link', { name: /project|projekt/i });
    expect(projectsLink).toHaveAttribute('href', '/projects');
  });

  it('marks rocket icon as aria-hidden', () => {
    const { container } = render(<StepComplete />);

    const hiddenIcons = container.querySelectorAll('[aria-hidden="true"]');
    expect(hiddenIcons.length).toBeGreaterThan(0);
  });

  it('renders checkmark icon', () => {
    const { container } = render(<StepComplete />);

    // CheckCircle2 renders as an SVG
    const svgs = container.querySelectorAll('svg');
    expect(svgs.length).toBeGreaterThan(0);
  });
});
