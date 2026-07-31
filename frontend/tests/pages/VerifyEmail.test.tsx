import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import VerifyEmail from '@/pages/VerifyEmail';
import { ForbiddenError, HttpError, RateLimitError, ServerError } from '@/lib/errors';

// Mock the API client (the page calls api.verifyEmail directly)
const mockVerifyEmail = vi.fn();
const mockResendVerification = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    verifyEmail: (token: string, password: string) => mockVerifyEmail(token, password),
    resendVerification: (email: string, password: string) =>
      mockResendVerification(email, password),
  },
}));

// Mock navigation and the token read from the URL query string
const mockNavigate = vi.fn();
const routeState: { token: string | null } = { token: 'valid-verify-token' };
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [{ get: () => routeState.token }, vi.fn()],
  };
});

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// AuthLayout renders Navbar, which calls useAuth -> mock it (as the other auth
// page tests do).
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

describe('VerifyEmail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routeState.token = 'valid-verify-token';
  });

  const getPasswordInput = () => screen.getByPlaceholderText('Enter your password');
  const getSubmitButton = () => screen.getByRole('button', { name: /confirm email/i });
  // Navbar always renders its own "Sign In" nav link, so a plain getByRole
  // would find two matches; filter down to the page's own link by href.
  const getLoginLink = () =>
    screen
      .getAllByRole('link', { name: /sign in/i })
      .find((link) => link.getAttribute('href') === '/login');

  it('renders the password field and submit button when a token is present', () => {
    render(<VerifyEmail />);

    expect(getPasswordInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
  });

  it('does not call api.verifyEmail on mount', async () => {
    render(<VerifyEmail />);

    // Flush a tick so a stray effect-driven auto-submit would have fired.
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockVerifyEmail).not.toHaveBeenCalled();
  });

  it('shows a missing-link message instead of a form when the token is absent', () => {
    routeState.token = null;
    render(<VerifyEmail />);

    expect(screen.queryByPlaceholderText('Enter your password')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /confirm email/i })).not.toBeInTheDocument();
    expect(getLoginLink()).toBeInTheDocument();
  });

  it('shows a loading state during submission', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockImplementation(() => new Promise(() => {}));
    render(<VerifyEmail />);

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/confirming/i)).toBeInTheDocument();
    });
  });

  it('calls api.verifyEmail with the token and password, then navigates to /login on success', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockResolvedValueOnce(undefined);
    render(<VerifyEmail />);

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockVerifyEmail).toHaveBeenCalledWith('valid-verify-token', 'CorrectHorse123!');
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: expect.any(String) })
    );
  });

  it('keeps the form and token in place on a 403 (wrong password), without navigating away', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new ForbiddenError());
    render(<VerifyEmail />);

    await user.type(getPasswordInput(), 'WrongPassword123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/password/i);
    });

    expect(getPasswordInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('replaces the form with a login link on a 400 (unusable link)', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new HttpError('Invalid or expired token', 400));
    render(<VerifyEmail />);

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.queryByPlaceholderText('Enter your password')).not.toBeInTheDocument();
    });

    expect(getLoginLink()).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows a distinct locked-out message on a 429, without navigating away', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new RateLimitError());
    render(<VerifyEmail />);

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/wait/i);
    });

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows a generic error toast for an unexpected failure (e.g. service unavailable)', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new ServerError());
    render(<VerifyEmail />);

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ variant: 'destructive' })
      );
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
