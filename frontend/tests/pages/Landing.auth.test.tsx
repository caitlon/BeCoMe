import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import Landing from '@/pages/Landing';

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: '1', email: 'test@test.com', first_name: 'Test', last_name: 'User', photo_url: null, created_at: '2025-01-01' },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Landing - Authenticated', () => {
  it('shows "Go to Projects" button linking to /projects', () => {
    render(<Landing />);
    const heroButton = screen.getByRole('link', { name: /go to projects/i });
    expect(heroButton).toHaveAttribute('href', '/projects');
  });

  it('CTA section links to /projects for authenticated users', () => {
    render(<Landing />);
    const ctaLinks = screen.getAllByRole('link').filter(
      link => link.getAttribute('href') === '/projects'
    );
    // Hero + CTA + Navbar = at least 2 links to /projects
    expect(ctaLinks.length).toBeGreaterThanOrEqual(2);
  });
});
