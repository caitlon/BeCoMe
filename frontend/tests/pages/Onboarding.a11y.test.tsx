import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import Onboarding from '@/pages/Onboarding';

const { mockUser, mockPathname } = vi.hoisted(() => ({
  mockUser: {
    id: 'user-1',
    email: 'john@example.com',
    first_name: 'John',
    last_name: 'Doe',
    photo_url: null,
    created_at: '2024-01-01T00:00:00Z',
  },
  mockPathname: { value: '/onboarding' },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useLocation: () => ({ pathname: mockPathname.value, search: '', hash: '', state: null, key: 'default' }),
  };
});

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Onboarding - Accessibility', () => {
  it('step nav has aria-label for step navigation', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const stepNav = screen.getByRole('navigation', { name: /step navigation|navigace kroků/i });
    expect(stepNav).toBeInTheDocument();
  });

  it('current step dot has aria-current="step"', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const currentDot = screen.getByRole('button', { name: /go to step 1/i });
    expect(currentDot).toHaveAttribute('aria-current', 'step');
  });

  it('non-current step dots do not have aria-current', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const otherDot = screen.getByRole('button', { name: /go to step 2/i });
    expect(otherDot).not.toHaveAttribute('aria-current');
  });

  it('each step dot has aria-label with step number', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    for (let i = 1; i <= 6; i++) {
      const dot = screen.getByRole('button', { name: new RegExp(`go to step ${i}`, 'i') });
      expect(dot).toBeInTheDocument();
    }
  });

  it('main content area has id="main-content"', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main-content');
  });

  it('useDocumentTitle sets correct title', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    expect(document.title).toContain('BeCoMe');
  });

  it('step dots are wrapped in nav element', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const stepNav = screen.getByRole('navigation', { name: /step navigation|navigace kroků/i });
    const buttons = within(stepNav).getAllByRole('button');
    expect(buttons).toHaveLength(6);
  });
});
