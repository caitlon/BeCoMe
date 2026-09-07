import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import Privacy from '@/pages/Privacy';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);
vi.mock('framer-motion', () => framerMotionMock);

/**
 * This page is a legal notice, so its only value is that every sentence matches the code.
 * The assertions below therefore pin the numbers and the claims rather than the layout:
 * a review on 2026-09-08 found seven statements that no longer matched the backend, and
 * the suite was green throughout because nothing tested the substance.
 *
 * When one of these fails, check the code before changing the number. The sources are
 * api/auth/cookies.py, api/config.py, api/routes/users.py and api/schemas/auth.py.
 */
describe('Privacy', () => {
  it('renders the page heading and every section', () => {
    render(<Privacy />);

    expect(screen.getByRole('heading', { name: 'Privacy', level: 1 })).toBeInTheDocument();
    for (const heading of [
      'Who is responsible',
      'What is stored',
      'Cookies',
      'Who else handles it',
      'How long',
      'On what basis',
      'Your rights, and how to use them',
      'If something is wrong',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    }
  });

  it('names the controller and offers a mailto link', () => {
    render(<Privacy />);

    expect(screen.getByRole('link', { name: 'xkuze010@studenti.czu.cz' })).toHaveAttribute(
      'href',
      'mailto:xkuze010@studenti.czu.cz'
    );
  });

  it('states the three cookies by name, with the lifetimes the API sets', () => {
    render(<Privacy />);

    expect(screen.getByText(/__Host-access_token .* It lasts 15 minutes\./)).toBeInTheDocument();
    expect(screen.getByText(/__Secure-refresh_token .* It lasts 7 days/)).toBeInTheDocument();
    expect(screen.getByText(/__Host-csrf_token protects forms/)).toBeInTheDocument();
  });

  it('gives the one-time link lifetimes the config sets', () => {
    render(<Privacy />);

    expect(screen.getByText(/password-reset link is valid for 60 minutes/)).toBeInTheDocument();
    expect(screen.getByText(/verification link is valid for 24 hours/)).toBeInTheDocument();
  });

  /** Seven days is the idle limit. A session in continuous use has no fixed maximum. */
  it('describes the session limit as idle rather than absolute', () => {
    render(<Privacy />);

    expect(screen.getByText(/no fixed maximum for a session in continuous use/)).toBeInTheDocument();
  });

  it('cites the lawful bases it relies on', () => {
    render(<Privacy />);

    expect(screen.getByText(/Article 6\(1\)\(b\) of the GDPR/)).toBeInTheDocument();
    expect(screen.getByText(/Article 6\(1\)\(f\)/)).toBeInTheDocument();
  });

  it('discloses the security logs and the IP addresses in them', () => {
    render(<Privacy />);

    expect(screen.getByText(/They record the IP address a sign-in/)).toBeInTheDocument();
    expect(screen.getByText(/keyed hash rather than in the clear/)).toBeInTheDocument();
  });

  /** Resend's endpoint is in the US, so Chapter V applies and the notice has to say so. */
  it('names every processor and flags the transfer outside the EU', () => {
    render(<Privacy />);

    for (const name of ['Railway hosts', 'Cloudflare serves', 'Resend delivers', 'Sentry receives', 'Better Stack receives']) {
      expect(screen.getByText(new RegExp(name))).toBeInTheDocument();
    }
    expect(screen.getByText(/transfer outside the European Union under Chapter V/)).toBeInTheDocument();
  });

  it('does not claim an email change the app cannot perform', () => {
    render(<Privacy />);

    expect(screen.getByText(/email address cannot be changed in the app/)).toBeInTheDocument();
    expect(screen.queryByText(/Correct your name or email/)).not.toBeInTheDocument();
  });

  /** Deletion is refused until every owned project has a disposition. */
  it('states the precondition on erasure', () => {
    render(<Privacy />);

    expect(screen.getByText(/Projects you own have to be dealt with first/)).toBeInTheDocument();
    expect(screen.getByText(/A project you hand over stays/)).toBeInTheDocument();
  });

  it('links to the profile, where export and erasure live', () => {
    render(<Privacy />);

    expect(screen.getByRole('link', { name: 'Go to your profile' })).toHaveAttribute(
      'href',
      '/profile'
    );
  });

  it('points at the supervisory authority', () => {
    render(<Privacy />);

    expect(screen.getByText(/Úřad pro ochranu osobních údajů/)).toBeInTheDocument();
  });
});
