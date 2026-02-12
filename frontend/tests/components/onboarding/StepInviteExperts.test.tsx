import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { StepInviteExperts } from '@/components/onboarding/StepInviteExperts';

vi.mock('framer-motion', () => framerMotionMock);

describe('StepInviteExperts', () => {
  it('renders heading', () => {
    render(<StepInviteExperts />);

    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
  });

  it('renders description', () => {
    const { container } = render(<StepInviteExperts />);

    const description = container.querySelector('.text-muted-foreground.text-center.max-w-md');
    expect(description).toBeInTheDocument();
  });

  it('renders email input as readOnly with aria-readonly', () => {
    render(<StepInviteExperts />);

    const emailInput = screen.getByRole('textbox');
    expect(emailInput).toHaveAttribute('readonly');
    expect(emailInput).toHaveAttribute('aria-readonly', 'true');
  });

  it('renders invite button with aria-label', () => {
    render(<StepInviteExperts />);

    const buttons = screen.getAllByRole('button');
    const inviteButton = buttons.find((btn) => btn.getAttribute('aria-label'));
    expect(inviteButton).toBeDefined();
  });

  it('renders two sample expert cards', () => {
    const { container } = render(<StepInviteExperts />);

    const sampleCards = container.querySelectorAll('.bg-muted.rounded-lg');
    expect(sampleCards).toHaveLength(2);
  });

  it('renders hint text', () => {
    const { container } = render(<StepInviteExperts />);

    const hint = container.querySelector('.text-xs.text-muted-foreground.italic');
    expect(hint).toBeInTheDocument();
  });
});
