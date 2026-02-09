import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { Footer } from '@/components/layout/Footer';

describe('Footer', () => {
  it('renders brand link to /', () => {
    render(<Footer />);

    const brandLink = screen.getByRole('link', { name: 'BeCoMe' });
    expect(brandLink).toHaveAttribute('href', '/');
  });

  it('renders product links', () => {
    render(<Footer />);

    expect(screen.getByRole('link', { name: /get started/i })).toHaveAttribute('href', '/register');
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: /about/i })).toHaveAttribute('href', '/about');
  });

  it('renders resource links', () => {
    render(<Footer />);

    expect(screen.getByRole('link', { name: /documentation/i })).toHaveAttribute('href', '/docs');
    expect(screen.getByRole('link', { name: /faq/i })).toHaveAttribute('href', '/faq');
  });

  it('external links have target="_blank" and rel="noopener noreferrer"', () => {
    render(<Footer />);

    const githubLinks = screen.getAllByRole('link', { name: /github/i });
    for (const link of githubLinks) {
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    }
  });

  it('displays copyright with current year', () => {
    render(<Footer />);

    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(`© ${year}`))).toBeInTheDocument();
  });
});
