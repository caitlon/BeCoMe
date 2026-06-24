import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import ResetPassword from '@/pages/ResetPassword';

// Mock the API client (the page calls api.resetPassword directly)
const mockResetPassword = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    resetPassword: (token: string, password: string) => mockResetPassword(token, password),
  },
}));

// Mock navigation and the reset token read from the URL query string
const mockNavigate = vi.fn();
const routeState: { token: string | null } = { token: 'valid-reset-token' };
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
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

// AuthLayout renders Navbar, which calls useAuth -> mock it (as Login/Register tests do)
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

describe('ResetPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routeState.token = 'valid-reset-token';
  });

  const getPasswordInput = () => screen.getByPlaceholderText('Min. 12 characters');
  const getConfirmInput = () => screen.getByPlaceholderText('Confirm your password');
  const getSubmitButton = () => screen.getByRole('button', { name: /reset password/i });

  it('renders the password and confirm fields when a token is present', () => {
    render(<ResetPassword />);

    expect(getPasswordInput()).toBeInTheDocument();
    expect(getConfirmInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
  });

  it('shows an invalid-link message when the token is missing', () => {
    routeState.token = null;
    render(<ResetPassword />);

    expect(screen.getByText(/this reset link is invalid/i)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /request a new link/i });
    expect(link).toHaveAttribute('href', '/forgot-password');
  });

  it('shows the password requirements checklist when typing', async () => {
    const user = userEvent.setup();
    render(<ResetPassword />);

    await user.type(getPasswordInput(), 'test');

    await waitFor(() => {
      expect(screen.getByText(/at least 12 characters/i)).toBeInTheDocument();
      expect(screen.getByText(/an uppercase letter/i)).toBeInTheDocument();
    });
  });

  it('shows an error when passwords do not match', async () => {
    const user = userEvent.setup();
    render(<ResetPassword />);

    await user.type(getPasswordInput(), 'TestPass123!@#');
    await user.type(getConfirmInput(), 'Different123!@#');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/passwords must match/i)).toBeInTheDocument();
    });
  });

  it('disables submit until the form is valid', () => {
    render(<ResetPassword />);

    expect(getSubmitButton()).toBeDisabled();
  });

  it('resets the password, shows success, and navigates to login', async () => {
    const user = userEvent.setup();
    mockResetPassword.mockResolvedValueOnce(undefined);
    render(<ResetPassword />);

    await user.type(getPasswordInput(), 'BrandNewPass456!');
    await user.type(getConfirmInput(), 'BrandNewPass456!');
    await waitFor(() => expect(getSubmitButton()).not.toBeDisabled());
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalledWith('valid-reset-token', 'BrandNewPass456!');
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
  });

  it('shows an error toast when the reset fails', async () => {
    const user = userEvent.setup();
    mockResetPassword.mockRejectedValueOnce(new Error('Invalid or expired reset token'));
    render(<ResetPassword />);

    await user.type(getPasswordInput(), 'BrandNewPass456!');
    await user.type(getConfirmInput(), 'BrandNewPass456!');
    await waitFor(() => expect(getSubmitButton()).not.toBeDisabled());
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ variant: 'destructive' })
      );
    });
  });
});
