import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import Landing from '@/pages/Landing';

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

// Mock framer-motion to avoid animation issues in tests
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

describe('Landing', () => {
  it('renders hero section with title', () => {
    render(<Landing />);

    expect(screen.getByText('Group Decisions,')).toBeInTheDocument();
    expect(screen.getByText('Precisely Measured')).toBeInTheDocument();
  });

  it('renders hero subtitle', () => {
    render(<Landing />);

    expect(
      screen.getByText(/aggregate expert opinions using fuzzy triangular numbers/i)
    ).toBeInTheDocument();
  });

  it('shows "Start Your Project" button for unauthenticated users', () => {
    render(<Landing />);

    const startButton = screen.getByRole('link', { name: /start your project/i });
    expect(startButton).toHaveAttribute('href', '/register');
  });

  it('renders "How It Works" section', () => {
    render(<Landing />);

    expect(screen.getByText('How It Works')).toBeInTheDocument();
    expect(screen.getByText('Collect')).toBeInTheDocument();
    expect(screen.getByText('Calculate')).toBeInTheDocument();
    expect(screen.getByText('Consensus')).toBeInTheDocument();
  });

  it('renders "Case Studies" section', () => {
    render(<Landing />);

    // "Case Studies" appears multiple times (heading and navbar link)
    const caseStudiesElements = screen.getAllByText('Case Studies');
    expect(caseStudiesElements.length).toBeGreaterThan(0);
  });

  it('renders CTA section', () => {
    render(<Landing />);

    expect(screen.getByText('Ready to find consensus?')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /get started free/i })).toBeInTheDocument();
  });

  it('has link to about page', () => {
    render(<Landing />);

    const learnMoreLink = screen.getByText(/learn more about the become method/i);
    expect(learnMoreLink).toHaveAttribute('href', '/about');
  });
});

describe('Landing - hash scrolling', () => {
  it('scrolls to element when URL has hash', () => {
    const mockScrollIntoView = vi.fn();
    const mockElement = document.createElement('div');
    mockElement.scrollIntoView = mockScrollIntoView;

    vi.spyOn(document, 'getElementById').mockReturnValue(mockElement);
    vi.useFakeTimers();

    render(<Landing />, { initialEntries: ['/#case-studies'] });

    vi.advanceTimersByTime(200);

    expect(mockScrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'center',
    });

    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('does nothing when hash element does not exist', () => {
    vi.spyOn(document, 'getElementById').mockReturnValue(null);

    // Should not throw
    render(<Landing />, { initialEntries: ['/#nonexistent'] });

    vi.restoreAllMocks();
  });
});
