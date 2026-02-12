import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { StepWelcome } from '@/components/onboarding/StepWelcome';

vi.mock('framer-motion', () => framerMotionMock);

describe('StepWelcome', () => {
  it('renders heading', () => {
    render(<StepWelcome />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('renders subtitle with primary color', () => {
    const { container } = render(<StepWelcome />);

    const subtitle = container.querySelector('.text-primary.font-medium');
    expect(subtitle).toBeInTheDocument();
  });

  it('renders description text', () => {
    const { container } = render(<StepWelcome />);

    const description = container.querySelector('.text-muted-foreground.max-w-md');
    expect(description).toBeInTheDocument();
  });

  it('renders Sparkles icon', () => {
    const { container } = render(<StepWelcome />);

    const svgs = container.querySelectorAll('svg');
    expect(svgs.length).toBeGreaterThan(0);
  });
});
