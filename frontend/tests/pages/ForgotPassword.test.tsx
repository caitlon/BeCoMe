import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import ForgotPassword from '@/pages/ForgotPassword';

// Mock the API client (the page calls api.forgotPassword directly)
const mockForgotPassword = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    forgotPassword: (email: string, turnstileToken?: string | null) =>
      mockForgotPassword(email, turnstileToken),
  },
}));

// A real TurnstileField needs Cloudflare's script, which never loads in this suite.
// The Turnstile-specific describe block below swaps in a fake that mints a token on
// click. No ref: unlike the other three forms, this page never resets the widget,
// because submitting replaces the whole form with the confirmation panel.
vi.mock('@/components/forms', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/forms')>();
  const { isTurnstileRequired } = await import('@/lib/turnstile');
  return {
    ...actual,
    TurnstileField: function TurnstileFieldMock({
      action,
      onToken,
    }: {
      action: string;
      onToken: (token: string | null) => void;
    }) {
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
    },
  };
});

// AuthLayout renders Navbar, which calls useAuth -> mock it (as Login/Register tests do)
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

describe('ForgotPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getEmailInput = () => screen.getByPlaceholderText('you@example.com');
  const getSubmitButton = () => screen.getByRole('button', { name: /send reset link/i });

  it('renders the email field and submit button', () => {
    render(<ForgotPassword />);

    expect(getEmailInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
  });

  it('sets autocomplete="email" so password managers fill the right field', () => {
    render(<ForgotPassword />);

    expect(getEmailInput()).toHaveAttribute('autocomplete', 'email');
  });

  it('shows a validation error for an invalid email', async () => {
    const user = userEvent.setup();
    render(<ForgotPassword />);

    await user.type(getEmailInput(), 'not-an-email');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/invalid.*email/i)).toBeInTheDocument();
    });
  });

  it('calls api.forgotPassword and shows a generic success message', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockResolvedValueOnce(undefined);
    render(<ForgotPassword />);

    await user.type(getEmailInput(), 'user@example.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      // Second argument is the Turnstile token; the check is off in this suite (no
      // VITE_TURNSTILE_SITE_KEY), so the widget never mints one and forgotPassword
      // is called with null exactly as it was before the bot check existed.
      expect(mockForgotPassword).toHaveBeenCalledWith('user@example.com', null);
    });
    await waitFor(() => {
      expect(screen.getByText(/if that email is registered/i)).toBeInTheDocument();
    });
  });

  it('shows the same success message even when the request fails (anti-enumeration)', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockRejectedValueOnce(new Error('boom'));
    render(<ForgotPassword />);

    await user.type(getEmailInput(), 'user@example.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/if that email is registered/i)).toBeInTheDocument();
    });
  });

  it('shows a loading state during submission', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockImplementation(() => new Promise(() => {}));
    render(<ForgotPassword />);

    await user.type(getEmailInput(), 'user@example.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/sending/i)).toBeInTheDocument();
    });
  });

  it('has a link back to login', () => {
    render(<ForgotPassword />);

    const loginLink = screen.getByRole('link', { name: /back to sign in/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });

  describe('Turnstile bot check', () => {
    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('renders the widget for the password_reset action and keeps submit disabled until it mints a token', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      const user = userEvent.setup();
      render(<ForgotPassword />);

      await user.type(getEmailInput(), 'user@example.com');

      // The exact defect this guards: a widget rendered under the wrong action (or
      // none) mints a token the API refuses as action_mismatch. ForgotPassword posts
      // to /auth/forgot-password, which the backend guards with "password_reset".
      const mintButton = screen.getByRole('button', { name: /mint password_reset token/i });
      const submitButton = getSubmitButton();
      expect(submitButton).toBeDisabled();

      await user.click(submitButton);
      expect(mockForgotPassword).not.toHaveBeenCalled();

      await user.click(mintButton);
      await waitFor(() => expect(submitButton).not.toBeDisabled());
    });

    it('sends the minted token and leaves no widget behind when the attempt fails', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockForgotPassword.mockRejectedValueOnce(new Error('boom'));
      const user = userEvent.setup();
      render(<ForgotPassword />);

      await user.type(getEmailInput(), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /mint password_reset token/i }));

      const submitButton = getSubmitButton();
      await waitFor(() => expect(submitButton).not.toBeDisabled());
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockForgotPassword).toHaveBeenCalledWith(
          'user@example.com',
          'mock-turnstile-token'
        );
      });

      // The other three forms reset the widget after a failure, because the user
      // stays on them and needs a live token for the retry. This one does not: the
      // failure is swallowed to keep the answer identical for a registered and an
      // unregistered address, so the confirmation panel replaces the form and takes
      // the widget with it. There is nothing left to hand a fresh token to.
      await waitFor(() => {
        expect(screen.getByText(/reset link is on its way/i)).toBeInTheDocument();
      });
      expect(
        screen.queryByRole('button', { name: /mint password_reset token/i })
      ).not.toBeInTheDocument();
    });
  });
});
