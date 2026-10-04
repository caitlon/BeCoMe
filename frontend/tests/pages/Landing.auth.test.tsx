import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import Landing from '@/pages/Landing';

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

describe('Landing - Authenticated', () => {
  it('shows "Go to Projects" in the hero and the call to action, both linking to /projects', () => {
    render(<Landing />);
    const main = within(screen.getByRole('main'));

    const buttons = main.getAllByRole('link', { name: /go to projects/i });
    expect(buttons).toHaveLength(2);
    buttons.forEach((button) => expect(button).toHaveAttribute('href', '/projects'));
    expect(screen.queryByRole('link', { name: 'Create Account' })).not.toBeInTheDocument();
  });
});
