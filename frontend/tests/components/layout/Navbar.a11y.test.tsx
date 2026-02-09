import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import { Navbar } from '@/components/layout/Navbar';

const { mockUser, mockLogout, mockPathname } = vi.hoisted(() => ({
  mockUser: {
    id: 'user-1',
    email: 'john@example.com',
    first_name: 'John',
    last_name: 'Doe',
    photo_url: null,
    created_at: '2024-01-01T00:00:00Z',
  },
  mockLogout: vi.fn(),
  mockPathname: { value: '/' },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: () => ({ pathname: mockPathname.value, search: '', hash: '', state: null, key: 'default' }),
  };
});

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    logout: mockLogout,
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Navbar - Accessibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.value = '/';
  });

  it('nav has aria-label for main navigation', () => {
    render(<Navbar />);

    const nav = screen.getByRole('navigation', { name: /main navigation|hlavní navigace/i });
    expect(nav).toBeInTheDocument();
  });

  it('About link has aria-current="page" when on /about', () => {
    mockPathname.value = '/about';
    render(<Navbar />);

    const aboutLink = screen.getByRole('link', { name: /about/i });
    expect(aboutLink).toHaveAttribute('aria-current', 'page');
  });

  it('About link has no aria-current when on /', () => {
    mockPathname.value = '/';
    render(<Navbar />);

    const aboutLink = screen.getByRole('link', { name: /about/i });
    expect(aboutLink).not.toHaveAttribute('aria-current');
  });

  it('Projects link has aria-current="page" when on /projects', () => {
    mockPathname.value = '/projects';
    render(<Navbar />);

    const projectsLink = screen.getByRole('link', { name: /projects/i });
    expect(projectsLink).toHaveAttribute('aria-current', 'page');
  });

  it('mobile menu button has aria-expanded="false" initially', () => {
    // Render at a small viewport (mobile menu button is md:hidden)
    render(<Navbar />);

    const menuButton = screen.getByRole('button', { name: /open menu|otevřít menu/i });
    expect(menuButton).toHaveAttribute('aria-expanded', 'false');
  });

  it('mobile menu button has aria-expanded="true" after click', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    const menuButton = screen.getByRole('button', { name: /open menu|otevřít menu/i });
    await user.click(menuButton);

    expect(menuButton).toHaveAttribute('aria-expanded', 'true');
  });

  it('mobile menu button has aria-controls="mobile-menu"', () => {
    render(<Navbar />);

    const menuButton = screen.getByRole('button', { name: /open menu|otevřít menu/i });
    expect(menuButton).toHaveAttribute('aria-controls', 'mobile-menu');
  });

  it('Escape key closes mobile menu', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    const menuButton = screen.getByRole('button', { name: /open menu|otevřít menu/i });
    await user.click(menuButton);

    expect(menuButton).toHaveAttribute('aria-expanded', 'true');

    await user.keyboard('{Escape}');

    // After Escape, menu closes and focus returns to the toggle button
    expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    expect(menuButton).toHaveFocus();
  });
});
