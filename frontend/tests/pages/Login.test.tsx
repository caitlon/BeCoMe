import { forwardRef, useImperativeHandle } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import Login from '@/pages/Login';
import {
  ServerError,
  RateLimitError,
  ForbiddenError,
  UnauthorizedError,
  TURNSTILE_REFUSED_CODE,
} from '@/lib/errors';

// The two 403s POST /auth/login can answer, exactly as the API sends them. Only the
// code tells them apart: the detail is prose, and the status is the same.
const notVerified403 = () =>
  new ForbiddenError('Email address not verified. Check your inbox for the activation link.');
const turnstileRefused403 = () =>
  new ForbiddenError(
    'Could not confirm you are human. Reload the page and try again.',
    TURNSTILE_REFUSED_CODE
  );

// Mock useAuth
const mockLogin = vi.fn();
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

// A real TurnstileField needs Cloudflare's script, which never loads in this suite.
// The Turnstile-specific describe block below swaps in a fake that mints a token on
// click and exposes reset() the same way the real widget does, so the page's own
// wiring (disabled-until-token, the action it asks for, reset-after-failure) can be
// exercised without simulating a real challenge.
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
      // Mirrors the real widget's own contract (renders nothing without a sitekey),
      // so every test that does not opt into Turnstile -- the whole file, minus the
      // describe block below, including the not-verified state's nested
      // ResendVerification and its own TurnstileField -- sees exactly what it saw
      // before this mock existed.
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

// The not-verified state's resend control calls api.resendVerification directly.
const mockResendVerification = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    resendVerification: (email: string, password: string) =>
      mockResendVerification(email, password),
  },
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getEmailInput = () => screen.getByPlaceholderText('you@example.com');
  const getPasswordInput = () => screen.getByPlaceholderText('Enter your password');

  it('renders login form with email and password fields', () => {
    render(<Login />);

    expect(getEmailInput()).toBeInTheDocument();
    expect(getPasswordInput()).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('sets autocomplete attributes so password managers fill the right field', () => {
    render(<Login />);

    expect(getEmailInput()).toHaveAttribute('autocomplete', 'email');
    expect(getPasswordInput()).toHaveAttribute('autocomplete', 'current-password');
  });

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup();
    render(<Login />);

    const emailInput = getEmailInput();
    await user.type(emailInput, 'invalid-email');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/invalid.*email/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for empty password', async () => {
    const user = userEvent.setup();
    render(<Login />);

    const passwordInput = getPasswordInput();
    await user.click(passwordInput);
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/password.*required/i)).toBeInTheDocument();
    });
  });

  it('shows loading state during submission', async () => {
    const user = userEvent.setup();
    mockLogin.mockImplementation(() => new Promise(() => {}));

    render(<Login />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/signing in/i)).toBeInTheDocument();
    });
  });

  it('calls login and navigates to /projects on success', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce(undefined);

    render(<Login />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      // Third argument is the Turnstile token; the check is off in this suite (no
      // VITE_TURNSTILE_SITE_KEY), so the widget never mints one and login is called
      // with null exactly as it was before the bot check existed.
      expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123', null);
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/projects');
    });

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: expect.any(String),
      })
    );
  });

  it('shows error toast on login failure', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));

    render(<Login />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'wrongpassword');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          description: 'Invalid credentials',
        })
      );
    });
  });

  it('shows a service-unavailable toast when login fails with a ServerError', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new ServerError());

    render(<Login />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          description: 'The service is temporarily unavailable. Please try again in a moment.',
        })
      );
    });
  });

  it('shows a too-many-attempts toast when login fails with a RateLimitError', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new RateLimitError());

    render(<Login />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          description: 'Too many attempts. Please wait a moment and try again.',
        })
      );
    });
  });

  it('has link to registration page', () => {
    render(<Login />);

    const registerLink = screen.getByRole('link', { name: /create one/i });
    expect(registerLink).toHaveAttribute('href', '/register');
  });


  it('disables submit while loading', async () => {
    const user = userEvent.setup();
    mockLogin.mockImplementation(() => new Promise(() => {}));

    render(<Login />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'password123');

    const submitButton = screen.getByRole('button', { name: /sign in/i });
    await user.click(submitButton);

    await waitFor(() => {
      const loadingButton = screen.getByRole('button', { name: /signing in/i });
      expect(loadingButton).toBeDisabled();
    });
  });

  describe('unverified account (403, no code)', () => {
    beforeEach(() => {
      mockResendVerification.mockReset();
    });

    it('shows a not-verified state with a resend control instead of the generic error toast', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(notVerified403());

      render(<Login />);

      await user.type(getEmailInput(), 'unverified@example.com');
      await user.type(getPasswordInput(), 'CorrectHorse123!');
      await user.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /resend/i })).toBeInTheDocument();
      });

      expect(mockToast).not.toHaveBeenCalledWith(
        expect.objectContaining({ variant: 'destructive' })
      );
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('does not offer a resend control on a 401 (bad credentials)', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(new UnauthorizedError('Invalid credentials'));

      render(<Login />);

      await user.type(getEmailInput(), 'test@example.com');
      await user.type(getPasswordInput(), 'wrongpassword');
      await user.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({ variant: 'destructive' })
        );
      });

      expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument();
    });

    it('resends the verification email using the address and password typed into the form', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(notVerified403());
      mockResendVerification.mockResolvedValueOnce(undefined);

      render(<Login />);

      await user.type(getEmailInput(), 'unverified@example.com');
      await user.type(getPasswordInput(), 'CorrectHorse123!');
      await user.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /resend/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /resend/i }));

      await waitFor(() => {
        expect(mockResendVerification).toHaveBeenCalledWith(
          'unverified@example.com',
          'CorrectHorse123!'
        );
      });
    });

    it('lets the user return to the login form from the not-verified state', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(notVerified403());

      render(<Login />);

      await user.type(getEmailInput(), 'unverified@example.com');
      await user.type(getPasswordInput(), 'CorrectHorse123!');
      await user.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /resend/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /try signing in again/i }));

      expect(getEmailInput()).toBeInTheDocument();
      expect(getEmailInput()).toHaveValue('unverified@example.com');
      expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument();
    });
  });

  describe('Turnstile bot check', () => {
    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('renders the widget for the login action and keeps submit disabled until it mints a token', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      const user = userEvent.setup();
      render(<Login />);

      await user.type(getEmailInput(), 'test@example.com');
      await user.type(getPasswordInput(), 'password123');

      // The exact defect this guards: a widget rendered under the wrong action (or
      // none at all) mints a token the API refuses as action_mismatch, so the
      // literal action string reaching the widget is what this asserts.
      const mintButton = screen.getByRole('button', { name: /mint login token/i });
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      expect(submitButton).toBeDisabled();

      await user.click(submitButton);
      expect(mockLogin).not.toHaveBeenCalled();

      await user.click(mintButton);
      await waitFor(() => expect(submitButton).not.toBeDisabled());
    });

    it('does not read a refused bot check as an unverified account', async () => {
      // The defect this guards: both refusals are 403 on this route, and claiming
      // every 403 as the unverified case meant that during a siteverify outage -
      // the check is fail-closed, so every sign-in is refused - each user was told
      // their long-verified account was unconfirmed, and pointed at a resend flow
      // guarded by the same check.
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockLogin.mockRejectedValueOnce(turnstileRefused403());
      const user = userEvent.setup();
      render(<Login />);

      await user.type(getEmailInput(), 'verified@example.com');
      await user.type(getPasswordInput(), 'CorrectHorse123!');
      await user.click(screen.getByRole('button', { name: /mint login token/i }));

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await waitFor(() => expect(submitButton).not.toBeDisabled());
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: 'destructive',
            description: "We couldn't confirm you are human. Please try again.",
          })
        );
      });

      expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument();
      expect(screen.queryByText(/hasn't confirmed its email address/i)).not.toBeInTheDocument();
      expect(getEmailInput()).toHaveValue('verified@example.com');
      // The refused token is spent, so the retry the toast invites needs a new one.
      expect(mockTurnstileReset).toHaveBeenCalled();
    });

    it('sends the minted token to login and resets the widget after a failed attempt', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));
      const user = userEvent.setup();
      render(<Login />);

      await user.type(getEmailInput(), 'test@example.com');
      await user.type(getPasswordInput(), 'password123');
      await user.click(screen.getByRole('button', { name: /mint login token/i }));

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await waitFor(() => expect(submitButton).not.toBeDisabled());
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith(
          'test@example.com',
          'password123',
          'mock-turnstile-token'
        );
      });
      // The token is spent by the attempt that just failed; without a reset the
      // next click would send that same dead token and be refused again.
      await waitFor(() => {
        expect(mockTurnstileReset).toHaveBeenCalled();
      });
    });
  });
});
