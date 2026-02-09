import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { filterMotionProps } from '@tests/utils';
import Documentation from '@/pages/Documentation';

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

describe('Documentation', () => {
  it('renders page heading', () => {
    render(<Documentation />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('TOC navigation has 5 buttons', () => {
    render(<Documentation />);

    const nav = screen.getByRole('navigation', { name: /table of contents|obsah/i });
    const buttons = nav.querySelectorAll('button');
    expect(buttons.length).toBe(5);
  });

  it('TOC nav has aria-label', () => {
    render(<Documentation />);

    const nav = screen.getByRole('navigation', { name: /table of contents|obsah/i });
    expect(nav).toBeInTheDocument();
  });

  it('Getting Started section with cards', () => {
    const { container } = render(<Documentation />);

    const gettingStarted = container.querySelector('#getting-started');
    expect(gettingStarted).toBeInTheDocument();
  });

  it('Glossary section with terms', () => {
    const { container } = render(<Documentation />);

    const glossary = container.querySelector('#glossary');
    expect(glossary).toBeInTheDocument();
  });

  it('main content area has id="main-content"', () => {
    const { container } = render(<Documentation />);

    const main = container.querySelector('main#main-content');
    expect(main).toBeInTheDocument();
  });
});
