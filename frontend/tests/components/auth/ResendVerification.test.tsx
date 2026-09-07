import { forwardRef, useImperativeHandle } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { ResendVerification } from '@/components/auth/ResendVerification';

const mockResendVerification = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    resendVerification: (email: string, password: string, turnstileToken?: string | null) =>
      mockResendVerification(email, password, turnstileToken),
  },
}));

// A real TurnstileField needs Cloudflare's script, which never loads in this suite.
// The Turnstile-specific describe block below swaps in a fake that mints a token on
// click and exposes reset() the same way the real widget does.
const mockTurnstileReset = vi.fn();
vi.mock('@/components/forms', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/forms')>();
  const { isTurnstileRequired } = await import('@/lib/turnstile');
  return {
    ...actual,
    TurnstileField: forwardRef<
      { reset: () => void },
      { action: string; onToken: (token: string | null) => void }
    >(function TurnstileFieldMock({ action, onToken }, ref) {
      useImperativeHandle(ref, () => ({ reset: mockTurnstileReset }));
      // Mirrors the real widget's own contract (renders nothing without a
      // sitekey), so every test that does not opt into Turnstile sees exactly
      // what it saw before this mock existed.
      if (!isTurnstileRequired()) {
        return null;
      }
      return (
        <button type="button" onClick={() => onToken('mock-turnstile-token')}>
          {`mint ${action} token`}
        </button>
      );
    }),
  };
});

describe('ResendVerification', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Anchored so it never collides with the Turnstile "mint resend_verification
  // token" button the mock below renders alongside it (that name also contains
  // "resend", since it echoes the action prop verbatim).
  const getButton = () =>
    screen.getByRole('button', { name: /^resend confirmation/i });

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
      // Third argument is the Turnstile token; the check is off in this suite (no
      // VITE_TURNSTILE_SITE_KEY), so the widget never mints one and resendVerification
      // is called with null exactly as it was before the bot check existed.
      expect(mockResendVerification).toHaveBeenCalledWith(
        'user@example.com',
        'CorrectHorse123!',
        null
      );
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

  describe('Turnstile bot check', () => {
    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('renders the widget for the resend_verification action and keeps the button disabled until it mints a token', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      const user = userEvent.setup();
      render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

      // The exact defect this guards: a widget rendered under the wrong action (or
      // none) mints a token the API refuses as action_mismatch.
      const mintButton = screen.getByRole('button', { name: /mint resend_verification token/i });
      expect(getButton()).toBeDisabled();

      await user.click(getButton());
      expect(mockResendVerification).not.toHaveBeenCalled();

      await user.click(mintButton);
      await waitFor(() => expect(getButton()).not.toBeDisabled());
    });

    it('sends the minted token to resendVerification and resets the widget after a failed attempt', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockResendVerification.mockRejectedValueOnce(new Error('boom'));
      const user = userEvent.setup();
      render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

      await user.click(screen.getByRole('button', { name: /mint resend_verification token/i }));
      await waitFor(() => expect(getButton()).not.toBeDisabled());
      await user.click(getButton());

      await waitFor(() => {
        expect(mockResendVerification).toHaveBeenCalledWith(
          'user@example.com',
          'CorrectHorse123!',
          'mock-turnstile-token'
        );
      });
      // The token is spent by the attempt that just failed; without a reset the
      // next click would send that same dead token and be refused again.
      await waitFor(() => {
        expect(mockTurnstileReset).toHaveBeenCalled();
      });
    });

    it('resets the widget after a successful send, so a second one cannot replay the token', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockResendVerification.mockResolvedValueOnce(undefined);
      const user = userEvent.setup();
      render(<ResendVerification email="user@example.com" password="CorrectHorse123!" />);

      await user.click(screen.getByRole('button', { name: /mint resend_verification token/i }));
      await waitFor(() => expect(getButton()).not.toBeDisabled());
      await user.click(getButton());

      await waitFor(() => {
        expect(screen.getByRole('status')).toBeInTheDocument();
      });
      // A success spends the token exactly as a failure does, and this control is the
      // one that stays on screen afterwards by design (the test above asserts it is
      // still enabled). Without a reset here, asking for a second link replays the
      // token the first one already redeemed and is refused for a reason the user
      // can do nothing about.
      await waitFor(() => {
        expect(mockTurnstileReset).toHaveBeenCalled();
      });
    });
  });
});
