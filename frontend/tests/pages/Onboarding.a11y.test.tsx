import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { filterMotionProps } from '@tests/utils';
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
    useLocation: () => ({ pathname: mockPathname.value }),
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

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...filterMotionProps(props)}>{children}</div>
    ),
    h1: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <h1 {...filterMotionProps(props)}>{children}</h1>
    ),
    h2: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <h2 {...filterMotionProps(props)}>{children}</h2>
    ),
    p: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <p {...filterMotionProps(props)}>{children}</p>
    ),
    nav: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <nav {...filterMotionProps(props)}>{children}</nav>
    ),
    span: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <span {...filterMotionProps(props)}>{children}</span>
    ),
    polygon: (props: Record<string, unknown>) => <polygon {...filterMotionProps(props)} />,
    circle: (props: Record<string, unknown>) => <circle {...filterMotionProps(props)} />,
    line: (props: Record<string, unknown>) => <line {...filterMotionProps(props)} />,
    section: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <section {...filterMotionProps(props)}>{children}</section>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren<object>) => <>{children}</>,
}));

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
    const { container } = render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const main = container.querySelector('main#main-content');
    expect(main).toBeInTheDocument();
  });

  it('useDocumentTitle sets correct title', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    expect(document.title).toContain('BeCoMe');
  });

  it('step dots are wrapped in nav element', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // The step navigation should contain all step dot buttons
    const stepNav = screen.getByRole('navigation', { name: /step navigation|navigace kroků/i });
    const buttons = stepNav.querySelectorAll('button');
    expect(buttons.length).toBe(6);
  });
});
