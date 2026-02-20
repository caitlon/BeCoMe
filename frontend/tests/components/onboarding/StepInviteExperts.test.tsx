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
    render(<StepInviteExperts />);

    expect(screen.getByText(/add team members/i)).toBeInTheDocument();
  });

  it('renders email input as readOnly', () => {
    render(<StepInviteExperts />);

    const emailInput = screen.getByRole('textbox');
    expect(emailInput).toHaveAttribute('readonly');
  });

  it('renders invite button with aria-label', () => {
    render(<StepInviteExperts />);

    expect(screen.getByRole('button', { name: /send invitation|odeslat/i })).toBeInTheDocument();
  });

  it('renders two sample expert cards', () => {
    render(<StepInviteExperts />);

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Anna Smith')).toBeInTheDocument();
  });

  it('renders hint text', () => {
    render(<StepInviteExperts />);

    expect(screen.getByText(/experts will see/i)).toBeInTheDocument();
  });
});
