import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
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
    const links = mobileMenu.querySelectorAll('a');
    const hrefs = Array.from(links).map((l) => l.getAttribute('href'));

    expect(hrefs).toContain('/login');
    expect(hrefs).toContain('/register');
  });

  it('clicking Sign In link closes mobile menu', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const loginLink = mobileMenu.querySelector('a[href="/login"]')!;
    await user.click(loginLink);

    expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument();
  });

  it('clicking Get Started link closes mobile menu', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const registerLink = mobileMenu.querySelector('a[href="/register"]')!;
    await user.click(registerLink);

    expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument();
  });
});
