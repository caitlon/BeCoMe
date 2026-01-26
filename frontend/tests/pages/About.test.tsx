import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import About from '@/pages/About';

// Mock useAuth
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

// Filter out framer-motion props from DOM elements
const filterMotionProps = (props: Record<string, unknown>) => {
  const motionProps = [
    'initial',
    'animate',
    'exit',
    'variants',
    'transition',
    'whileHover',
    'whileTap',
    'whileInView',
    'viewport',
  ];
  const filtered: Record<string, unknown> = {};
  for (const key of Object.keys(props)) {
    if (!motionProps.includes(key)) {
      filtered[key] = props[key];
    }
  }
  return filtered;
};

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...filterMotionProps(props)}>{children}</div>
    ),
    h1: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <h1 {...filterMotionProps(props)}>{children}</h1>
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
  },
  AnimatePresence: ({ children }: React.PropsWithChildren<object>) => <>{children}</>,
}));

describe('About', () => {
  it('renders page title', () => {
    render(<About />);

    expect(screen.getByText('About BeCoMe')).toBeInTheDocument();
  });

  it('renders hero subtitle', () => {
    render(<About />);

    expect(
      screen.getByText(/best compromise mean — a scientific method/i)
    ).toBeInTheDocument();
  });

  it('renders "The Challenge" section', () => {
    render(<About />);

    expect(screen.getByText('The Challenge')).toBeInTheDocument();
  });

  it('renders "The BeCoMe Method" section', () => {
    render(<About />);

    expect(screen.getByText('The BeCoMe Method')).toBeInTheDocument();
  });

  it('renders "Applications" section with list items', () => {
    render(<About />);

    expect(screen.getByText('Applications')).toBeInTheDocument();
    expect(screen.getByText('State security decisions')).toBeInTheDocument();
    expect(screen.getByText('Public health policy')).toBeInTheDocument();
    expect(screen.getByText('Flood prevention')).toBeInTheDocument();
  });

  it('renders "Authors" section with names', () => {
    render(<About />);

    expect(screen.getByText('Authors')).toBeInTheDocument();
    // Authors appear in multiple places (navbar and content), use getAllByText
    const vranaNames = screen.getAllByText('Prof. Ing. Ivan Vrana, DrSc.');
    expect(vranaNames.length).toBeGreaterThan(0);
    const tyrychtrNames = screen.getAllByText('Ing. Jan Tyrychtr, PhD.');
    expect(tyrychtrNames.length).toBeGreaterThan(0);
  });

  it('has link to documentation', () => {
    render(<About />);

    const docsLink = screen.getByRole('link', { name: /view documentation/i });
    expect(docsLink).toHaveAttribute('href', '/docs');
  });

  it('has link to register page', () => {
    render(<About />);

    const registerLink = screen.getByRole('link', { name: /start your project/i });
    expect(registerLink).toHaveAttribute('href', '/register');
  });

  it('has link to case studies', () => {
    render(<About />);

    const caseStudiesLink = screen.getByRole('link', { name: /view case studies/i });
    expect(caseStudiesLink).toHaveAttribute('href', '/#case-studies');
  });
});
