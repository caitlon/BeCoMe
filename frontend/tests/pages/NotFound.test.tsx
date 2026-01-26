import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import NotFound from '@/pages/NotFound';

// Mock useAuth
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

describe('NotFound', () => {
  it('renders 404 heading', () => {
    render(<NotFound />);

    expect(screen.getByRole('heading', { name: '404' })).toBeInTheDocument();
  });

  it('renders description text', () => {
    render(<NotFound />);

    expect(screen.getByText(/page.*not.*found|doesn't exist/i)).toBeInTheDocument();
  });

  it('has link to home page', () => {
    render(<NotFound />);

    const homeLink = screen.getByRole('link', { name: /home|back/i });
    expect(homeLink).toHaveAttribute('href', '/');
  });
});
