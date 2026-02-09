import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render, filterMotionProps } from '@tests/utils';
import CaseStudy from '@/pages/CaseStudy';

const { mockParams } = vi.hoisted(() => ({
  mockParams: { value: { id: 'budget' } },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => mockParams.value,
    useLocation: () => ({ pathname: '/case-studies/budget' }),
  };
});

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...filterMotionProps(props)}>{children}</div>
    ),
    section: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <section {...filterMotionProps(props)}>{children}</section>
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

describe('CaseStudy - Budget', () => {
  beforeEach(() => {
    mockParams.value = { id: 'budget' };
  });

  it('renders case study title for valid ID', () => {
    render(<CaseStudy />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('renders expert count and data type', () => {
    render(<CaseStudy />);

    // The "22 experts" span uses font-mono
    expect(screen.getByText(/22\s+experts/i)).toBeInTheDocument();
    expect(screen.getByText(/interval scale/i)).toBeInTheDocument();
  });

  it('renders question in blockquote', () => {
    const { container } = render(<CaseStudy />);

    const blockquote = container.querySelector('blockquote');
    expect(blockquote).toBeInTheDocument();
    expect(blockquote?.textContent).toBeTruthy();
  });

  it('renders results card with best compromise', () => {
    render(<CaseStudy />);

    expect(screen.getByText('57.3')).toBeInTheDocument();
  });

  it('renders opinion table with expert rows', () => {
    render(<CaseStudy />);

    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();

    // Budget case has 22 experts
    const rows = table.querySelectorAll('tbody tr');
    expect(rows.length).toBe(22);
  });

  it('main content area has id="main-content"', () => {
    const { container } = render(<CaseStudy />);

    const main = container.querySelector('main#main-content');
    expect(main).toBeInTheDocument();
  });
});

describe('CaseStudy - Not Found', () => {
  beforeEach(() => {
    mockParams.value = { id: 'nonexistent' };
  });

  it('renders not-found state for invalid ID', () => {
    render(<CaseStudy />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('not-found state has link to /', () => {
    render(<CaseStudy />);

    const homeLink = screen.getByRole('link', { name: /back|home|zpět/i });
    expect(homeLink).toHaveAttribute('href', '/');
  });
});
