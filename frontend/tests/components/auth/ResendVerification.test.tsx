import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { ResendVerification } from '@/components/auth/ResendVerification';

const mockResendVerification = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    resendVerification: (email: string, password: string) =>
      mockResendVerification(email, password),
  },
}));

describe('ResendVerification', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getButton = () =>
    screen.getByRole('button', { name: /resend/i });

  it('renders a button to resend the verification email', () => {
    render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

    expect(getButton()).toBeInTheDocument();
  });

  it('calls api.resendVerification with the email and password on click', async () => {
    const user = userEvent.setup();
    mockResendVerification.mockResolvedValueOnce(undefined);
    render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

    await user.click(getButton());

    await waitFor(() => {
      expect(mockResendVerification).toHaveBeenCalledWith('user@example.com', 'CorrectHorse123!');
    });
  });

  it('shows a loading state while the request is in flight', async () => {
    const user = userEvent.setup();
    mockResendVerification.mockImplementation(() => new Promise(() => {}));
    render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

    await user.click(getButton());

    await waitFor(() => {
      expect(screen.getByText(/sending/i)).toBeInTheDocument();
    });
  });

  it('shows a success message once the resend request resolves', async () => {
    const user = userEvent.setup();
    mockResendVerification.mockResolvedValueOnce(undefined);
    render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

    await user.click(getButton());

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/on its way/i);
    });
  });

  it('shows an error message when the resend request fails', async () => {
    const user = userEvent.setup();
    mockResendVerification.mockRejectedValueOnce(new Error('boom'));
    render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

    await user.click(getButton());

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('allows retrying after a failure', async () => {
    const user = userEvent.setup();
    mockResendVerification.mockRejectedValueOnce(new Error('boom'));
    render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

    await user.click(getButton());
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    mockResendVerification.mockResolvedValueOnce(undefined);
    await user.click(getButton());

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/on its way/i);
    });
    expect(mockResendVerification).toHaveBeenCalledTimes(2);
  });

  it('is not disabled after a successful send, so the user can request another one', async () => {
    const user = userEvent.setup();
    mockResendVerification.mockResolvedValueOnce(undefined);
    render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

    await user.click(getButton());
    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    expect(getButton()).not.toBeDisabled();
  });
});
