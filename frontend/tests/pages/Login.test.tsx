import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import Login from '@/pages/Login';

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

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
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

  it('has link to registration page', () => {
    render(<Login />);

    const registerLink = screen.getByRole('link', { name: /create one/i });
    expect(registerLink).toHaveAttribute('href', '/register');
  });

  it('has forgot password button', () => {
    render(<Login />);

    expect(screen.getByRole('button', { name: /forgot password/i })).toBeInTheDocument();
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
});
