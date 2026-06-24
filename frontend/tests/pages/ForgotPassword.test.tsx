import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import ForgotPassword from '@/pages/ForgotPassword';

// Mock the API client (the page calls api.forgotPassword directly)
const mockForgotPassword = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    forgotPassword: (email: string) => mockForgotPassword(email),
  },
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
      expect(mockForgotPassword).toHaveBeenCalledWith('user@example.com');
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
});
