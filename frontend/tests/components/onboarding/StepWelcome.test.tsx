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

  it('renders subtitle', () => {
    render(<StepWelcome />);

    expect(screen.getByText(/best compromise mean/i)).toBeInTheDocument();
  });

  it('renders description text', () => {
    render(<StepWelcome />);

    expect(screen.getByText(/learn how to use the platform/i)).toBeInTheDocument();
  });
});
