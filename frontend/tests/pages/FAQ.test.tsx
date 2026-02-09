import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { filterMotionProps } from '@tests/utils';
import FAQ from '@/pages/FAQ';

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

describe('FAQ', () => {
  it('renders page heading', () => {
    render(<FAQ />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('renders 5 category sections', () => {
    render(<FAQ />);

    // 5 category headings (h2) inside main content
    const h2s = screen.getAllByRole('heading', { level: 2 });
    // At least 5 category sections + possible CTA h2
    expect(h2s.length).toBeGreaterThanOrEqual(5);
  });

  it('sidebar nav buttons present', () => {
    render(<FAQ />);

    // 5 categories as nav buttons
    const nav = screen.getByRole('navigation', { name: /categories|kategorie/i });
    const buttons = nav.querySelectorAll('button');
    expect(buttons.length).toBe(5);
  });

  it('sidebar nav has aria-label', () => {
    render(<FAQ />);

    const nav = screen.getByRole('navigation', { name: /categories|kategorie/i });
    expect(nav).toBeInTheDocument();
  });

  it('accordion items render question text', () => {
    render(<FAQ />);

    // Check for at least one accordion trigger (question)
    const triggers = screen.getAllByRole('button');
    // Filter for accordion triggers (they have data-state attribute from Radix)
    const accordionTriggers = triggers.filter((btn) => btn.hasAttribute('data-state'));
    expect(accordionTriggers.length).toBeGreaterThan(0);
  });

  it('CTA section with link to /docs', () => {
    render(<FAQ />);

    // The CTA section has a link to docs
    const docsLinks = screen.getAllByRole('link').filter(
      (link) => link.getAttribute('href') === '/docs'
    );
    expect(docsLinks.length).toBeGreaterThanOrEqual(1);
  });

  it('main content area has id="main-content"', () => {
    const { container } = render(<FAQ />);

    const main = container.querySelector('#main-content');
    expect(main).toBeInTheDocument();
  });
});
