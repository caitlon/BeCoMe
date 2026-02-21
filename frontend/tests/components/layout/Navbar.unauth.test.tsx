import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import { Navbar } from '@/components/layout/Navbar';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: () => ({ pathname: '/', search: '', hash: '', state: null, key: 'default' }),
  };
});

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);
vi.mock('framer-motion', () => framerMotionMock);

describe('Navbar - Unauthenticated Mobile Menu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('mobile menu shows Sign In and Get Started links', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const links = within(mobileMenu).getAllByRole('link');
    const hrefs = links.map((l) => l.getAttribute('href'));

    expect(hrefs).toContain('/login');
    expect(hrefs).toContain('/register');
  });

  it('clicking Sign In link closes mobile menu', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const loginLink = within(mobileMenu).getByRole('link', { name: /sign in/i });
    await user.click(loginLink);

    expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument();
  });

  it('clicking Get Started link closes mobile menu', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const registerLink = within(mobileMenu).getByRole('link', { name: /get started/i });
    await user.click(registerLink);

    expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument();
  });
});
