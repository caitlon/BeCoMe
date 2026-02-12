import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { StepCreateProject } from '@/components/onboarding/StepCreateProject';

vi.mock('framer-motion', () => framerMotionMock);

describe('StepCreateProject', () => {
  it('renders heading', () => {
    render(<StepCreateProject />);

    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
  });

  it('renders description', () => {
    render(<StepCreateProject />);

    expect(screen.getByText(/start by creating/i)).toBeInTheDocument();
  });

  it('renders 5 readOnly inputs', () => {
    render(<StepCreateProject />);

    const inputs = screen.getAllByRole('textbox');
    const numberInputs = screen.getAllByRole('spinbutton');
    const allInputs = [...inputs, ...numberInputs];

    expect(allInputs).toHaveLength(5);
    for (const input of allInputs) {
      expect(input).toHaveAttribute('readonly');
    }
  });

  it('has fieldset with sr-only legend', () => {
    const { container } = render(<StepCreateProject />);

    const fieldset = container.querySelector('fieldset');
    expect(fieldset).toBeInTheDocument();

    const legend = fieldset?.querySelector('legend');
    expect(legend).toBeInTheDocument();
    expect(legend?.className).toContain('sr-only');
  });

  it('renders hint text', () => {
    render(<StepCreateProject />);

    expect(screen.getByText(/the scale defines/i)).toBeInTheDocument();
  });
});
