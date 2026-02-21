import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import Profile from '@/pages/Profile';

// Mock useNavigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

// Mock api
vi.mock('@/lib/api', () => ({
  api: {
    updateCurrentUser: vi.fn(),
    changePassword: vi.fn(),
    deleteAccount: vi.fn(),
    uploadPhoto: vi.fn(),
    deletePhoto: vi.fn(),
  },
}));

// Mock useToast
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

// Mock useAuth with null user (loading state)
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: true,
    isAuthenticated: false,
    refreshUser: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Profile - Loading State', () => {
  it('shows loading spinner when user is null', () => {
    render(<Profile />);

    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument();
  });

  it('does not render profile form when user is null', () => {
    render(<Profile />);

    expect(screen.queryByText('Edit Profile')).not.toBeInTheDocument();
    expect(screen.queryByText('Change Password')).not.toBeInTheDocument();
    expect(screen.queryByText('Danger Zone')).not.toBeInTheDocument();
  });
});
