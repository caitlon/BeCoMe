import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import NotFound from '@/pages/NotFound';
import { logger } from '@/lib/logger';

// Mock useAuth
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

describe('NotFound', () => {
  beforeEach(() => {
    // Silence and observe the expected 404 log emitted on mount
    vi.spyOn(logger, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

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

  it('logs the 404 through the app logger', () => {
    render(<NotFound />);

    expect(logger.error).toHaveBeenCalledWith(
      expect.stringContaining('404'),
      expect.objectContaining({ path: expect.any(String) })
    );
  });
});
