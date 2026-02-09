import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import { StepEnterOpinion } from '@/components/onboarding/StepEnterOpinion';

vi.mock('framer-motion', () => framerMotionMock);

describe('StepEnterOpinion', () => {
  it('renders 3 number inputs', () => {
    render(<StepEnterOpinion />);

    expect(screen.getByLabelText(/lower|dolní/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/peak|vrchol/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/upper|horní/i)).toBeInTheDocument();
  });

  it('displays default values (30, 50, 70)', () => {
    render(<StepEnterOpinion />);

    expect(screen.getByLabelText(/lower|dolní/i)).toHaveValue(30);
    expect(screen.getByLabelText(/peak|vrchol/i)).toHaveValue(50);
    expect(screen.getByLabelText(/upper|horní/i)).toHaveValue(70);
  });

  it('renders triangle preview SVG with role="img"', () => {
    render(<StepEnterOpinion />);

    const svg = screen.getByRole('img');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('aria-labelledby', 'triangle-preview-title');
  });

  it('shows valid triangle when lower <= peak <= upper', () => {
    const { container } = render(<StepEnterOpinion />);

    // With defaults 30, 50, 70 — triangle should render (polygon present)
    const polygon = container.querySelector('polygon');
    expect(polygon).toBeInTheDocument();
  });

  it('shows error text when triangle is invalid (lower > peak)', async () => {
    const user = userEvent.setup();
    render(<StepEnterOpinion />);

    const lowerInput = screen.getByLabelText(/lower|dolní/i);

    // Clear and type 80 (> peak=50)
    await user.clear(lowerInput);
    await user.type(lowerInput, '80');

    // The error text from the preview should be visible
    const svg = screen.getByRole('img');
    const errorText = svg.querySelector('text');
    expect(errorText).toBeInTheDocument();
    expect(errorText?.textContent).toBeTruthy();
  });

  it('updates triangle when inputs change', async () => {
    const user = userEvent.setup();
    const { container } = render(<StepEnterOpinion />);

    const peakInput = screen.getByLabelText(/peak|vrchol/i);
    await user.clear(peakInput);
    await user.type(peakInput, '60');

    // Triangle still valid (30 <= 60 <= 70) — polygon should exist
    const polygon = container.querySelector('polygon');
    expect(polygon).toBeInTheDocument();
  });
});
