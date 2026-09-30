import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { Footer } from '@/components/layout/Footer';

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: '1', email: 'test@test.com', first_name: 'Test', last_name: 'User', photo_url: null, created_at: '2025-01-01' },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

describe('Footer - Authenticated', () => {
  it('shows one "Go to Projects" link to /projects and no "Create Account" link', () => {
    render(<Footer />);

    expect(screen.queryByRole('link', { name: 'Create Account' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to Projects' })).toHaveAttribute('href', '/projects');
  });
});
