import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import About from '@/pages/About';

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

vi.mock('framer-motion', () => framerMotionMock);

describe('About - Authenticated', () => {
  it('shows one "Go to Projects" link to /projects and no "Create Account" link', () => {
    render(<About />);

    expect(screen.queryByRole('link', { name: 'Create Account' })).not.toBeInTheDocument();
    const main = within(screen.getByRole('main'));
    expect(main.getByRole('link', { name: 'Go to Projects' })).toHaveAttribute('href', '/projects');
    // Call to action and footer
    expect(screen.getAllByRole('link', { name: 'Go to Projects' })).toHaveLength(2);
  });
});
