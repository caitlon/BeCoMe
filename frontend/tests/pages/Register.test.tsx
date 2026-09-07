import { forwardRef, useImperativeHandle } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import Register from '@/pages/Register';

// Registration no longer signs anyone in, so the page calls api.register
// directly instead of going through AuthContext.
const mockApiRegister = vi.fn();
const mockResendVerification = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    register: (data: unknown, turnstileToken?: string | null) =>
      mockApiRegister(data, turnstileToken),
    resendVerification: (email: string, password: string) =>
      mockResendVerification(email, password),
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
      // Mirrors the real widget's own contract (renders nothing without a sitekey),
      // so every test that does not opt into Turnstile -- the whole file, minus the
      // describe block below, including the check-inbox state's nested
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

// AuthLayout renders Navbar, which calls useAuth -> mock it (as the other auth
// page tests do), even though Register itself no longer reads auth state.
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

// Mock useNavigate so a regression that reintroduces a redirect is caught.
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

describe('Register', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getEmailInput = () => screen.getByPlaceholderText('you@example.com');
  const getPasswordInput = () => screen.getByPlaceholderText('Min. 12 characters');
  const getConfirmPasswordInput = () => screen.getByPlaceholderText('Confirm your password');
  const getFirstNameInput = () => screen.getByPlaceholderText('John');
  const getLastNameInput = () => screen.getByPlaceholderText('Doe');
  const getSubmitButton = () => screen.getByRole('button', { name: /create account/i });

  const fillValidForm = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'TestPass123!@#');
    await user.type(getConfirmPasswordInput(), 'TestPass123!@#');
    await user.type(getFirstNameInput(), 'John');
    await user.type(getLastNameInput(), 'Doe');
    await waitFor(() => expect(getSubmitButton()).not.toBeDisabled());
  };

  it('renders registration form with all fields', () => {
    render(<Register />);

    expect(getEmailInput()).toBeInTheDocument();
    expect(getPasswordInput()).toBeInTheDocument();
    expect(getConfirmPasswordInput()).toBeInTheDocument();
    expect(getFirstNameInput()).toBeInTheDocument();
    expect(getLastNameInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
  });

  it('sets autocomplete attributes so password managers fill the right field', () => {
    render(<Register />);

    expect(getEmailInput()).toHaveAttribute('autocomplete', 'email');
    expect(getPasswordInput()).toHaveAttribute('autocomplete', 'new-password');
    expect(getConfirmPasswordInput()).toHaveAttribute('autocomplete', 'new-password');
    expect(getFirstNameInput()).toHaveAttribute('autocomplete', 'given-name');
    expect(getLastNameInput()).toHaveAttribute('autocomplete', 'family-name');
  });

  it('shows email requirements checklist when email entered', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getEmailInput(), 'test');

    await waitFor(() => {
      expect(screen.getByText(/an @ symbol/i)).toBeInTheDocument();
      expect(screen.getByText(/a domain/i)).toBeInTheDocument();
      expect(screen.getByText(/no spaces/i)).toBeInTheDocument();
    });
  });

  it('shows password requirements checklist when password entered', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getPasswordInput(), 'test');

    await waitFor(() => {
      expect(screen.getByText(/at least 12 characters/i)).toBeInTheDocument();
      expect(screen.getByText(/an uppercase letter/i)).toBeInTheDocument();
      expect(screen.getByText(/a lowercase letter/i)).toBeInTheDocument();
      expect(screen.getByText(/a number/i)).toBeInTheDocument();
      expect(screen.getByText(/a special character/i)).toBeInTheDocument();
    });
  });

  it('validates password meets 12+ characters requirement', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getPasswordInput(), 'Pass1!');
    await user.tab();

    await waitFor(() => {
      const errorElement = document.getElementById('password-error');
      expect(errorElement).toBeInTheDocument();
      expect(errorElement?.textContent).toContain('12 characters');
    });
  });

  it('validates password has uppercase letter', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getPasswordInput(), 'password1');
    await user.tab();

    await waitFor(() => {
      const errorElement = document.getElementById('password-error');
      expect(errorElement).toBeInTheDocument();
    });
  });

  it('validates password has lowercase letter', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getPasswordInput(), 'PASSWORD1');
    await user.tab();

    await waitFor(() => {
      const errorElement = document.getElementById('password-error');
      expect(errorElement).toBeInTheDocument();
    });
  });

  it('validates password has number', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getPasswordInput(), 'Password');
    await user.tab();

    await waitFor(() => {
      const errorElement = document.getElementById('password-error');
      expect(errorElement).toBeInTheDocument();
    });
  });

  it('shows error when passwords do not match', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getPasswordInput(), 'TestPass123!@#');
    await user.type(getConfirmPasswordInput(), 'TestPass456!@#');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/passwords must match/i)).toBeInTheDocument();
    });
  });

  it('validates first name format', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getFirstNameInput(), 'John123');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/name can only contain letters/i)).toBeInTheDocument();
    });
  });

  it('validates last name format', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getLastNameInput(), 'Doe456');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/name can only contain letters/i)).toBeInTheDocument();
    });
  });

  it('submit button is disabled until form is valid', () => {
    render(<Register />);

    expect(getSubmitButton()).toBeDisabled();
  });

  it('shows loading state during submission', async () => {
    const user = userEvent.setup();
    mockApiRegister.mockImplementation(() => new Promise(() => {}));

    render(<Register />);
    await fillValidForm(user);
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/creating account/i)).toBeInTheDocument();
    });
  });

  it('shows the check-your-inbox state on success and does not navigate to /projects', async () => {
    const user = userEvent.setup();
    mockApiRegister.mockResolvedValueOnce(undefined);

    render(<Register />);
    await fillValidForm(user);
    await user.click(getSubmitButton());

    await waitFor(() => {
      // Second argument is the Turnstile token; the check is off in this suite (no
      // VITE_TURNSTILE_SITE_KEY), so the widget never mints one and register is
      // called with null exactly as it was before the bot check existed.
      expect(mockApiRegister).toHaveBeenCalledWith(
        {
          email: 'test@example.com',
          password: 'TestPass123!@#',
          first_name: 'John',
          last_name: 'Doe',
        },
        null
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/check your inbox/i)).toBeInTheDocument();
    });
    // The registered address is carried into the inbox message.
    expect(screen.getByText(/test@example\.com/)).toBeInTheDocument();

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /create account/i })).not.toBeInTheDocument();
  });

  it('shows error toast on registration failure and stays on the form', async () => {
    const user = userEvent.setup();
    mockApiRegister.mockRejectedValueOnce(new Error('That domain cannot receive email'));

    render(<Register />);
    await fillValidForm(user);
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          description: 'That domain cannot receive email',
        })
      );
    });

    expect(screen.queryByText(/check your inbox/i)).not.toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('offers a resend control in the inbox state that resends with the submitted credentials', async () => {
    const user = userEvent.setup();
    mockApiRegister.mockResolvedValueOnce(undefined);
    mockResendVerification.mockResolvedValueOnce(undefined);

    render(<Register />);
    await fillValidForm(user);
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/check your inbox/i)).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /resend/i }));

    await waitFor(() => {
      expect(mockResendVerification).toHaveBeenCalledWith(
        'test@example.com',
        'TestPass123!@#'
      );
    });
  });

  it('has link to login page', () => {
    render(<Register />);

    // Find sign-in links and verify at least one points to /login
    const loginLinks = screen.getAllByRole('link', { name: /sign in/i });
    const loginLink = loginLinks.find(
      (link) => link.getAttribute('href') === '/login'
    );
    expect(loginLink).toBeInTheDocument();
  });

  describe('Turnstile bot check', () => {
    afterEach(() => {
      vi.unstubAllEnvs();
    });

    // fillValidForm waits for the submit button to become enabled, which (with the
    // check switched on) also needs a token: these two tests fill the fields by
    // hand so a valid-but-token-less form can be observed as still disabled.
    const fillFieldsOnly = async (user: ReturnType<typeof userEvent.setup>) => {
      await user.type(getEmailInput(), 'test@example.com');
      await user.type(getPasswordInput(), 'TestPass123!@#');
      await user.type(getConfirmPasswordInput(), 'TestPass123!@#');
      await user.type(getFirstNameInput(), 'John');
      await user.type(getLastNameInput(), 'Doe');
    };

    it('renders the widget for the register action and keeps submit disabled until it mints a token', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      const user = userEvent.setup();
      render(<Register />);
      await fillFieldsOnly(user);

      // A valid form alone must not be enough: the exact defect this guards is a
      // widget rendered under the wrong action (or none), which mints a token the
      // API refuses as action_mismatch.
      const mintButton = screen.getByRole('button', { name: /mint register token/i });
      expect(getSubmitButton()).toBeDisabled();

      await user.click(mintButton);
      await waitFor(() => expect(getSubmitButton()).not.toBeDisabled());
    });

    it('sends the minted token to register and resets the widget after a failed attempt', async () => {
      vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key');
      mockApiRegister.mockRejectedValueOnce(new Error('That domain cannot receive email'));
      const user = userEvent.setup();
      render(<Register />);
      await fillFieldsOnly(user);

      await user.click(screen.getByRole('button', { name: /mint register token/i }));
      const submitButton = getSubmitButton();
      await waitFor(() => expect(submitButton).not.toBeDisabled());
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockApiRegister).toHaveBeenCalledWith(
          expect.objectContaining({ email: 'test@example.com' }),
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
