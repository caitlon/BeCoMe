import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import i18n from '@/i18n';
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

    expect(screen.getByRole('button', { name: 'Invite' })).toBeInTheDocument();
  });

  it('labels the invite button in Czech', async () => {
    await i18n.changeLanguage('cs');
    try {
      render(<StepInviteExperts />);

      expect(screen.getByRole('button', { name: 'Pozvat' })).toBeInTheDocument();
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('renders two sample expert cards', () => {
    render(<StepInviteExperts />);

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Anna Smith')).toBeInTheDocument();
  });

  it('renders hint text', () => {
    render(<StepInviteExperts />);

    expect(
      screen.getByText('No email is sent. Experts see the invitation in their "Invitations" tab.'),
    ).toBeInTheDocument();
  });

  it('renders hint text in Czech', async () => {
    await i18n.changeLanguage('cs');
    try {
      render(<StepInviteExperts />);

      expect(
        screen.getByText('E-mail se neposílá. Experti uvidí pozvánku v záložce "Pozvánky".'),
      ).toBeInTheDocument();
    } finally {
      await i18n.changeLanguage('en');
    }
  });
});
