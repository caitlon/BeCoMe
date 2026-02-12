import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { FooterMinimal } from '@/components/layout/FooterMinimal';

describe('FooterMinimal', () => {
  it('renders brand link to /', () => {
    render(<FooterMinimal />);

    const brandLink = screen.getByRole('link', { name: 'BeCoMe' });
    expect(brandLink).toHaveAttribute('href', '/');
  });

  it('renders About link to /about', () => {
    render(<FooterMinimal />);

    expect(screen.getByRole('link', { name: /about/i })).toHaveAttribute('href', '/about');
  });

  it('renders GitHub link with target="_blank" and noopener', () => {
    render(<FooterMinimal />);

    const githubLink = screen.getByRole('link', { name: /github/i });
    expect(githubLink).toHaveAttribute('target', '_blank');
    expect(githubLink).toHaveAttribute('rel', 'noopener noreferrer');
    expect(githubLink).toHaveAttribute('href', 'https://github.com/caitlon/BeCoMe');
  });

  it('displays copyright with current year', () => {
    render(<FooterMinimal />);

    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(`© ${year}`))).toBeInTheDocument();
  });
});
