import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import Login from '@/pages/Login';
import { ServerError, RateLimitError, ForbiddenError, UnauthorizedError } from '@/lib/errors';

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
      expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123');
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

  describe('unverified account (403)', () => {
    beforeEach(() => {
      mockResendVerification.mockReset();
    });

    it('shows a not-verified state with a resend control instead of the generic error toast', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(new ForbiddenError('Account not verified'));

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
      mockLogin.mockRejectedValueOnce(new ForbiddenError());
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
      mockLogin.mockRejectedValueOnce(new ForbiddenError());

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
});
