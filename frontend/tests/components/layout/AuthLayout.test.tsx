import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { AuthLayout } from '@/components/layout/AuthLayout';

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    logout: vi.fn(),
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('AuthLayout', () => {
  it('renders title as heading', () => {
    render(<AuthLayout title="Welcome Back">content</AuthLayout>);
    expect(screen.getByRole('heading', { name: 'Welcome Back' })).toBeInTheDocument();
  });

  it('renders children', () => {
    render(<AuthLayout title="Title"><p>Child content here</p></AuthLayout>);
    expect(screen.getByText('Child content here')).toBeInTheDocument();
  });

  it('has main element with id for accessibility', () => {
    render(<AuthLayout title="Title">content</AuthLayout>);
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content');
  });

  it('renders navigation', () => {
    render(<AuthLayout title="Title">content</AuthLayout>);
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });
});
