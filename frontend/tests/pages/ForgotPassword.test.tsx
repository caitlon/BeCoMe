import { forwardRef, useImperativeHandle } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import i18n from '@/i18n';
import ForgotPassword from '@/pages/ForgotPassword';
import {
  ForbiddenError,
  NetworkError,
  RateLimitError,
  ServerError,
  TURNSTILE_REFUSED_CODE,
} from '@/lib/errors';

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock the API client (the page calls api.forgotPassword directly)
const mockForgotPassword = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    forgotPassword: (email: string, language: string, turnstileToken?: string | null) =>
      mockForgotPassword(email, language, turnstileToken),
  },
}));

// A real TurnstileField needs Cloudflare's script, which never loads in this suite.
// The Turnstile-specific describe block below swaps in a fake that mints a token on
// click and exposes reset() the same way the real widget does, as a spy, so the tests
// can see the widget being reset after a refused bot check or a 429.
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

  it('shows no email error when the empty field is left before any submit attempt', async () => {
    const user = userEvent.setup();
    render(<ForgotPassword />);

    await user.click(getEmailInput());
    await user.tab();
    await act(async () => {});

    expect(screen.queryByText(/invalid.*email/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/email.*required/i)).not.toBeInTheDocument();
    expect(getEmailInput()).not.toHaveAttribute('aria-invalid', 'true');
  });

  it('asks for the email when the form is submitted with it empty', async () => {
    const user = userEvent.setup();
    render(<ForgotPassword />);

    await user.click(getSubmitButton());

    expect(await screen.findByText('Email is required')).toBeInTheDocument();
    expect(screen.queryByText(/invalid.*email/i)).not.toBeInTheDocument();
    expect(getEmailInput()).toHaveAttribute('aria-invalid', 'true');
    expect(mockForgotPassword).not.toHaveBeenCalled();
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
      // Second argument is the interface language, third the Turnstile token; the
      // check is off in this suite (no VITE_TURNSTILE_SITE_KEY), so the widget never
      // mints one and forgotPassword is called with null exactly as it was before the
      // bot check existed.
      expect(mockForgotPassword).toHaveBeenCalledWith('user@example.com', 'en', null);
    });
    await waitFor(() => {
      expect(screen.getByText(/if that email is registered/i)).toBeInTheDocument();
    });
  });

  // The reset email is written in the language the visitor is using, so the page
  // hands the API its interface language, the way the registration page does.
  it.each([
    ['en', 'en'],
    ['cs', 'cs'],
  ])('sends the language for interface language %s as %s', async (interfaceLanguage, expected) => {
    const user = userEvent.setup();
    mockForgotPassword.mockResolvedValueOnce(undefined);
    render(<ForgotPassword />);
    await user.type(getEmailInput(), 'user@example.com');
    const submit = getSubmitButton();

    // The visitor switches language after typing, as the switcher allows.
    await act(async () => {
      await i18n.changeLanguage(interfaceLanguage);
    });
    try {
      await user.click(submit);

      await waitFor(() => {
        expect(mockForgotPassword).toHaveBeenCalledWith('user@example.com', expected, null);
      });
    } finally {
      await act(async () => {
        await i18n.changeLanguage('en');
      });
    }
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

  // Only what is decided before the address is read may surface (the bot check and
  // the per-IP limiter). A server fault can be specific to a registered address, so
  // a 5xx or a dropped connection must look the same as success.
  it.each([
    ['a 5xx response', new ServerError('Service Unavailable', 503)],
    ['a network failure', new NetworkError()],
  ])('still shows the confirmation panel on %s (anti-enumeration)', async (_label, error) => {
    const user = userEvent.setup();
    mockForgotPassword.mockRejectedValueOnce(error);
    render(<ForgotPassword />);

    await user.type(getEmailInput(), 'user@example.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/if that email is registered/i)).toBeInTheDocument();
    });
    expect(mockToast).not.toHaveBeenCalled();
  });

  it('does not claim a link was sent when the request was rate limited', async () => {
    const user = userEvent.setup();
    mockForgotPassword.mockRejectedValueOnce(new RateLimitError('Too many requests', 45));
    render(<ForgotPassword />);

    await user.type(getEmailInput(), 'user@example.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith({
        title: 'Request failed',
        description: 'Too many attempts. Please try again in 45s.',
        variant: 'destructive',
      });
    });
    expect(screen.queryByText(/if that email is registered/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/reset link is on its way/i)).not.toBeInTheDocument();
    expect(getEmailInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
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
          'en',
          'mock-turnstile-token'
        );
      });

      // An ordinary failure is swallowed to keep the answer identical for a
      // registered and an unregistered address, so the confirmation panel replaces
      // the form and takes the widget with it. There is nothing left to hand a fresh
      // token to. A refused bot check is the one exception — see the test below.
      await waitFor(() => {
        expect(screen.getByText(/reset link is on its way/i)).toBeInTheDocument();
      });
      expect(
        screen.queryByRole('button', { name: /mint password_reset token/i })
      ).not.toBeInTheDocument();
    });

    it('does not claim a link was sent when the bot check refused the request', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockForgotPassword.mockRejectedValueOnce(
        new ForbiddenError('Bot check failed.', TURNSTILE_REFUSED_CODE)
      );
      const user = userEvent.setup();
      render(<ForgotPassword />);

      await user.type(getEmailInput(), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /mint password_reset token/i }));

      const submitButton = getSubmitButton();
      await waitFor(() => expect(submitButton).not.toBeDisabled());
      await user.click(submitButton);

      await waitFor(() => expect(mockForgotPassword).toHaveBeenCalled());
      await waitFor(() => expect(mockTurnstileReset).toHaveBeenCalled());

      // Nothing was sent, so the confirmation panel would be a lie — and it would
      // unmount the widget, leaving the user with no way to earn a fresh challenge.
      // The form stays put with the widget on it.
      expect(screen.queryByText(/reset link is on its way/i)).not.toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /mint password_reset token/i })
      ).toBeInTheDocument();
    });

    it('keeps the widget and the form when the request was rate limited', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockForgotPassword.mockRejectedValueOnce(new RateLimitError('Too many requests'));
      const user = userEvent.setup();
      render(<ForgotPassword />);

      await user.type(getEmailInput(), 'user@example.com');
      await user.click(screen.getByRole('button', { name: /mint password_reset token/i }));

      const submitButton = getSubmitButton();
      await waitFor(() => expect(submitButton).not.toBeDisabled());
      await user.click(submitButton);

      await waitFor(() => expect(mockForgotPassword).toHaveBeenCalled());

      // The bot check runs before the limiter, so its token is already spent: the
      // widget is reset and the submit button locks until it mints a fresh one.
      await waitFor(() => expect(mockTurnstileReset).toHaveBeenCalled());
      await waitFor(() => expect(getSubmitButton()).toBeDisabled());
      expect(screen.queryByText(/reset link is on its way/i)).not.toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /mint password_reset token/i })
      ).toBeInTheDocument();
    });
  });
});
