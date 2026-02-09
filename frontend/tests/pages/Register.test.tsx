import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import Register from '@/pages/Register';

// Mock useAuth
const mockRegister = vi.fn();
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    register: mockRegister,
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

describe('Register', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getEmailInput = () => screen.getByPlaceholderText('you@example.com');
  const getPasswordInput = () => screen.getByPlaceholderText('Min. 8 characters');
  const getConfirmPasswordInput = () => screen.getByPlaceholderText('Confirm your password');
  const getFirstNameInput = () => screen.getByPlaceholderText('John');
  const getLastNameInput = () => screen.getByPlaceholderText('Doe');
  const getSubmitButton = () => screen.getByRole('button', { name: /create account/i });

  it('renders registration form with all fields', () => {
    render(<Register />);

    expect(getEmailInput()).toBeInTheDocument();
    expect(getPasswordInput()).toBeInTheDocument();
    expect(getConfirmPasswordInput()).toBeInTheDocument();
    expect(getFirstNameInput()).toBeInTheDocument();
    expect(getLastNameInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
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
      expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
      expect(screen.getByText(/an uppercase letter/i)).toBeInTheDocument();
      expect(screen.getByText(/a lowercase letter/i)).toBeInTheDocument();
      expect(screen.getByText(/a number/i)).toBeInTheDocument();
    });
  });

  it('validates password meets 8+ characters requirement', async () => {
    const user = userEvent.setup();
    render(<Register />);

    await user.type(getPasswordInput(), 'Pass1');
    await user.tab();

    await waitFor(() => {
      const errorElement = document.getElementById('password-error');
      expect(errorElement).toBeInTheDocument();
      expect(errorElement?.textContent).toContain('8 characters');
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

    await user.type(getPasswordInput(), 'Password1');
    await user.type(getConfirmPasswordInput(), 'Password2');
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
    mockRegister.mockImplementation(() => new Promise(() => {}));

    render(<Register />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'Password1');
    await user.type(getConfirmPasswordInput(), 'Password1');
    await user.type(getFirstNameInput(), 'John');
    await user.type(getLastNameInput(), 'Doe');

    await waitFor(() => {
      expect(getSubmitButton()).not.toBeDisabled();
    });

    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/creating account/i)).toBeInTheDocument();
    });
  });

  it('calls register and navigates to /projects on success', async () => {
    const user = userEvent.setup();
    mockRegister.mockResolvedValueOnce(undefined);

    render(<Register />);

    await user.type(getEmailInput(), 'test@example.com');
    await user.type(getPasswordInput(), 'Password1');
    await user.type(getConfirmPasswordInput(), 'Password1');
    await user.type(getFirstNameInput(), 'John');
    await user.type(getLastNameInput(), 'Doe');

    await waitFor(() => {
      expect(getSubmitButton()).not.toBeDisabled();
    });

    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith(
        'test@example.com',
        'Password1',
        'John',
        'Doe'
      );
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/projects');
    });
  });

  it('shows error toast on registration failure', async () => {
    const user = userEvent.setup();
    mockRegister.mockRejectedValueOnce(new Error('Email already exists'));

    render(<Register />);

    await user.type(getEmailInput(), 'existing@example.com');
    await user.type(getPasswordInput(), 'Password1');
    await user.type(getConfirmPasswordInput(), 'Password1');
    await user.type(getFirstNameInput(), 'John');
    await user.type(getLastNameInput(), 'Doe');

    await waitFor(() => {
      expect(getSubmitButton()).not.toBeDisabled();
    });

    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          description: 'Email already exists',
        })
      );
    });
  });

  it('has link to login page', () => {
    render(<Register />);

    const loginLinks = screen.getAllByRole('link', { name: /sign in/i });
    const cardLoginLink = loginLinks.find(
      (link) => link.classList.contains('text-foreground')
    );
    expect(cardLoginLink).toBeInTheDocument();
    expect(cardLoginLink).toHaveAttribute('href', '/login');
  });
});
