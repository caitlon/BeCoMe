import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render, unauthenticatedAuthMock } from '@tests/utils';
import { Footer } from '@/components/layout/Footer';
import * as AuthContext from '@/contexts/AuthContext';
import { createUser } from '@tests/factories/user';

vi.mock('@/contexts/AuthContext', () => ({ useAuth: vi.fn() }));

describe('Footer', () => {
  beforeEach(() => {
    vi.mocked(AuthContext.useAuth).mockImplementation(unauthenticatedAuthMock.useAuth);
  });

  it('renders brand link to /', () => {
    render(<Footer />);

    const brandLink = screen.getByRole('link', { name: 'BeCoMe' });
    expect(brandLink).toHaveAttribute('href', '/');
  });

  it('renders product links', () => {
    render(<Footer />);

    expect(screen.getByRole('link', { name: /create account/i })).toHaveAttribute('href', '/register');
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: /about/i })).toHaveAttribute('href', '/about');
  });

  it('renders resource links', () => {
    render(<Footer />);

    expect(screen.getByRole('link', { name: /documentation/i })).toHaveAttribute('href', '/docs');
    expect(screen.getByRole('link', { name: /faq/i })).toHaveAttribute('href', '/faq');
    expect(screen.getByRole('link', { name: /privacy/i })).toHaveAttribute('href', '/privacy');
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

  it('offers the way to the projects, not sign-in, to a signed-in user', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      ...unauthenticatedAuthMock.useAuth(),
      status: 'authenticated',
      isAuthenticated: true,
      user: createUser({ id: '1' }),
    });
    render(<Footer />);

    expect(screen.getByRole('link', { name: /go to projects/i })).toHaveAttribute('href', '/projects');
    expect(screen.queryByRole('link', { name: /sign in/i })).not.toBeInTheDocument();
  });
});
