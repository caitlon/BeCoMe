import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import CaseStudy from '@/pages/CaseStudy';

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useParams: () => ({ id: 'budget' }),
    useLocation: () => ({ pathname: '/case-studies/budget', search: '', hash: '', state: null, key: 'default' }),
  };
});

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

describe('CaseStudy - Authenticated', () => {
  it('shows one "Go to Projects" link to /projects and no "Create Account" link', () => {
    render(<CaseStudy />);

    expect(screen.queryByRole('link', { name: 'Create Account' })).not.toBeInTheDocument();
    // The call to action in the page content; the footer carries the same link
    const main = within(screen.getByRole('main'));
    expect(main.getByRole('link', { name: 'Go to Projects' })).toHaveAttribute('href', '/projects');
  });
});
