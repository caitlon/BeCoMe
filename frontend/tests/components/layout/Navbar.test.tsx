import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, within, act, waitFor, renderHook } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import { Navbar } from '@/components/layout/Navbar';
import { useToast } from '@/hooks/use-toast';

// Use vi.hoisted for mock variables
const { mockUser, mockLogout, mockPathname } = vi.hoisted(() => ({
  mockUser: {
    id: 'user-1',
    email: 'john@example.com',
    first_name: 'John',
    last_name: 'Doe' as string | null,
    photo_url: null as string | null,
    created_at: '2024-01-01T00:00:00Z',
  },
  mockLogout: vi.fn(),
  mockPathname: { value: '/' },
}));

// Mock react-router
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useLocation: () => ({ pathname: mockPathname.value, search: '', hash: '', state: null, key: 'default' }),
  };
});

// Mock AuthContext
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    logout: mockLogout,
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Navbar - Authenticated', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.value = '/';
  });

  it('renders logo linking to landing when authenticated', () => {
    render(<Navbar />);

    const logo = screen.getByRole('link', { name: /become/i });
    expect(logo).toHaveAttribute('href', '/');
  });

  it('renders About link', () => {
    render(<Navbar />);

    expect(screen.getByRole('link', { name: /about/i })).toHaveAttribute('href', '/about');
  });

  it('renders Docs link', () => {
    render(<Navbar />);

    expect(screen.getByRole('link', { name: /docs/i })).toHaveAttribute('href', '/docs');
  });

  it('renders FAQ link', () => {
    render(<Navbar />);

    expect(screen.getByRole('link', { name: /faq/i })).toHaveAttribute('href', '/faq');
  });

  it('renders Case Studies link', () => {
    render(<Navbar />);

    expect(screen.getByRole('link', { name: /case studies/i })).toHaveAttribute('href', '/case-studies');
  });

  it('renders Projects link for authenticated users', () => {
    render(<Navbar />);

    expect(screen.getByRole('link', { name: /projects/i })).toHaveAttribute('href', '/projects');
  });

  it('displays user name in dropdown trigger', () => {
    render(<Navbar />);

    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  it('renders Take Tour link', () => {
    render(<Navbar />);

    expect(screen.getByRole('link', { name: /take.*tour/i })).toHaveAttribute('href', '/onboarding');
  });
});

describe('Navbar - Avatar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.photo_url = null;
  });

  it('displays initials fallback when no photo', () => {
    render(<Navbar />);

    expect(screen.getByText('JD')).toBeInTheDocument();
  });

  it('still shows initials fallback in jsdom even with photo_url', () => {
    mockUser.photo_url = 'https://example.com/photo.jpg';

    render(<Navbar />);

    // Radix AvatarImage requires real image loading which jsdom cannot do,
    // so fallback is always shown in test environment
    expect(screen.getByText('JD')).toBeInTheDocument();
  });
});

// Note: Unauthenticated navbar tests require different mock setup
// that would need vi.resetModules() which is complex with the current pattern.
// The authenticated flow is the primary use case and is well tested above.

describe('Navbar - User Menu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens dropdown on click', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    const trigger = screen.getByText('John Doe');
    await user.click(trigger);

    // Dropdown should show profile and logout options
    expect(screen.getByRole('menuitem', { name: /profile/i })).toBeInTheDocument();
  });

  it('has profile link in dropdown', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByText('John Doe'));

    const profileLink = screen.getByRole('menuitem', { name: /profile/i });
    expect(profileLink).toBeInTheDocument();
  });

  it('has logout option in dropdown', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByText('John Doe'));

    expect(screen.getByRole('menuitem', { name: /log out|sign out/i })).toBeInTheDocument();
  });

  it('clicking logout calls logout', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByText('John Doe'));

    const logoutItem = screen.getByRole('menuitem', { name: /log out|sign out/i });
    await user.click(logoutItem);

    expect(mockLogout).toHaveBeenCalled();
  });
});

describe('Navbar - Long user name', () => {
  const longName = { first: 'Bohumila', last: 'Novotná-Dvořáková' };
  const fullName = `${longName.first} ${longName.last}`;

  beforeEach(() => {
    mockUser.first_name = longName.first;
    mockUser.last_name = longName.last;
  });

  afterEach(() => {
    mockUser.first_name = 'John';
    mockUser.last_name = 'Doe';
  });

  // 9rem: with this cap the widest signed-in Czech row measured (1110px) still fits
  // inside 1280px, with 35px between the logo and the row, or 18px beside a 17px scrollbar.
  it('caps the name in the desktop row and keeps the full name in title and the DOM', () => {
    render(<Navbar />);

    const name = screen.getByText(fullName);

    expect(name).toHaveAttribute('title', fullName);
    expect(name).toHaveClass('truncate', 'max-w-36');
  });

  it('leaves no trailing space in the text or the title when there is no last name', () => {
    mockUser.last_name = null;
    render(<Navbar />);

    const name = screen.getByTitle(longName.first);

    expect(name.textContent).toBe(longName.first);
  });

  it('keeps the full name in the accessible name of the user menu button', () => {
    render(<Navbar />);

    expect(screen.getByRole('button', { name: new RegExp(fullName) })).toBeInTheDocument();
  });
});

describe('Navbar - Scroll Effect', () => {
  it('updates isScrolled state on scroll', () => {
    render(<Navbar />);
    const nav = screen.getByRole('navigation');

    act(() => {
      Object.defineProperty(globalThis, 'scrollY', { value: 50, writable: true });
      globalThis.dispatchEvent(new Event('scroll'));
    });
    expect(nav.className).toContain('shadow');

    act(() => {
      Object.defineProperty(globalThis, 'scrollY', { value: 0, writable: true });
      globalThis.dispatchEvent(new Event('scroll'));
    });
    expect(nav.className).not.toContain('shadow');
  });
});

describe('Navbar - Breakpoint', () => {
  // Measured in Chromium at 1280px, Czech, signed in: the desktop row is 1001px wide
  // with the name "Anna" and 1110px with a 26-character name capped at 9rem. The
  // logo (86px) and the container padding (48px) come on top, so the signed-in row
  // needs 1135px to 1244px. That rules out lg (1024px) and md (768px); the switch to
  // the menu button sits at xl (1280px). Signed out, the same row is 799px in Czech
  // and 706px in English.
  it('shows the desktop row from xl up and hides it below', () => {
    render(<Navbar />);

    const desktopRow = screen.getByRole('link', { name: /about/i }).parentElement;

    expect(desktopRow).toHaveClass('hidden', 'xl:flex');
    expect(desktopRow).not.toHaveClass('lg:flex');
    expect(desktopRow).not.toHaveClass('md:flex');
  });

  it('shows the menu button below xl and hides it from xl up', () => {
    render(<Navbar />);

    const menuControls = screen.getByRole('button', { name: /open menu/i }).parentElement;

    expect(menuControls).toHaveClass('xl:hidden');
    expect(menuControls).not.toHaveClass('lg:hidden');
    expect(menuControls).not.toHaveClass('md:hidden');
  });

  it('hides the open mobile menu from xl up', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    expect(mobileMenu).toHaveClass('xl:hidden');
    expect(mobileMenu).not.toHaveClass('lg:hidden');
    expect(mobileMenu).not.toHaveClass('md:hidden');
  });
});

describe('Navbar - Mobile Menu (authenticated)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.value = '/';
  });

  it('opens mobile menu when hamburger is clicked', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    const hamburger = screen.getByRole('button', { name: /open menu/i });
    await user.click(hamburger);

    expect(screen.getByRole('region', { name: /mobile/i })).toBeInTheDocument();
  });

  it('mobile menu contains nav links', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    expect(mobileMenu).toBeInTheDocument();

    // Check for authenticated mobile links
    const links = within(mobileMenu).getAllByRole('link');
    const hrefs = links.map((l) => l.getAttribute('href'));
    expect(hrefs).toContain('/about');
    expect(hrefs).toContain('/projects');
    expect(hrefs).toContain('/profile');
  });

  it('clicking a mobile nav link closes the menu', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const aboutLink = within(mobileMenu).getByRole('link', { name: /about/i });
    await user.click(aboutLink);

    // Menu should close, and the hamburger label returns to "Open menu"
    expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument();
  });

  it('clicking authenticated mobile link (Projects) closes menu', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const projectsLink = within(mobileMenu).getByRole('link', { name: /projects/i });
    await user.click(projectsLink);

    expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument();
  });

  it('mobile logout button calls handleLogout', async () => {
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByRole('button', { name: /open menu/i }));

    const mobileMenu = screen.getByRole('region', { name: /mobile/i });
    const logoutButton = within(mobileMenu).getByRole('button', { name: /sign out|log out/i });
    await user.click(logoutButton);

    expect(mockLogout).toHaveBeenCalled();
  });
});

describe('Navbar - Logout Outcome', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    // A plain object stand-in avoids happy-dom's real navigation handling, so the
    // assertions below can tell "navigated" and "stayed put" apart reliably.
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
    });
  });

  it('navigates home after a successful sign-out', async () => {
    mockLogout.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    render(<Navbar />);

    await user.click(screen.getByText('John Doe'));
    await user.click(screen.getByRole('menuitem', { name: /log out|sign out/i }));

    await waitFor(() => {
      expect(window.location.href).toBe('/');
    });
  });

  it('stays put and shows a destructive toast when sign-out fails', async () => {
    mockLogout.mockRejectedValueOnce(new Error('Network error'));
    const user = userEvent.setup();
    const { result } = renderHook(() => useToast());

    render(<Navbar />);
    await user.click(screen.getByText('John Doe'));
    await user.click(screen.getByRole('menuitem', { name: /log out|sign out/i }));

    await waitFor(() => {
      expect(result.current.toasts[0]).toMatchObject({
        title: 'Sign-out failed',
        description: 'Sign-out did not go through. Your session may still be active. Please try again.',
        variant: 'destructive',
      });
    });
    expect(window.location.href).toBe('');
  });
});
