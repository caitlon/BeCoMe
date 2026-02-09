import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import FAQ from '@/pages/FAQ';

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('FAQ', () => {
  it('renders page heading', () => {
    render(<FAQ />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('renders 5 category sections', () => {
    render(<FAQ />);

    const h2s = screen.getAllByRole('heading', { level: 2 });
    expect(h2s.length).toBeGreaterThanOrEqual(5);
  });

  it('sidebar nav has 5 category buttons', () => {
    render(<FAQ />);

    const nav = screen.getByRole('navigation', { name: /categories|kategorie/i });
    const buttons = within(nav).getAllByRole('button');
    expect(buttons).toHaveLength(5);
  });

  it('accordion items render question text', () => {
    render(<FAQ />);

    // Accordion triggers are buttons inside the main content (not sidebar nav)
    const nav = screen.getByRole('navigation', { name: /categories|kategorie/i });
    const allButtons = screen.getAllByRole('button');
    const navButtons = within(nav).getAllByRole('button');
    // Accordion triggers = all buttons minus nav buttons
    const accordionTriggers = allButtons.filter((btn) => !navButtons.includes(btn));
    expect(accordionTriggers.length).toBeGreaterThan(0);
  });

  it('CTA section with link to /docs', () => {
    render(<FAQ />);

    const docsLinks = screen.getAllByRole('link', { name: /documentation|dokumentace/i });
    const docsLink = docsLinks.find((link) => link.getAttribute('href') === '/docs');
    expect(docsLink).toBeDefined();
  });

  it('main content area has id="main-content"', () => {
    render(<FAQ />);

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main-content');
  });
});
