import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import Privacy from '@/pages/Privacy';
import enPrivacy from '@/i18n/locales/en/privacy.json';
import csPrivacy from '@/i18n/locales/cs/privacy.json';

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

    // the scope matters: it is every request, not only the auth events
    expect(screen.getByText(/Every request to the API is recorded/)).toBeInTheDocument();
    expect(screen.getByText(/the IP address it came from/)).toBeInTheDocument();
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

/**
 * The rendering tests above resolve to English, so until this block existed the Czech notice
 * was unasserted: a review on 2026-09-08 inverted "the email cannot be changed" in `cs` and
 * all 23 tests stayed green. Czech is the version a reader at the Czech supervisory authority
 * would open, so the facts are pinned in both files directly rather than through the page.
 *
 * "three days" is here for a different reason. It is the one number that cannot be re-derived
 * from this repository: it is the Better Stack source retention, read from the provider on
 * 2026-09-08. Three separate reviewers guessed it came from `_LOG_FILE_BACKUP_COUNT = 3`,
 * which is a rotated-file count on a handler no deployment enables. Pinning it makes any
 * future change deliberate instead of a silent drift away from what the provider does.
 */
describe.each([
  ['en', enPrivacy, {
    accessToken: '15 minutes', refresh: '7 days', reset: '60 minutes',
    verify: '24 hours', logs: 'three days',
    noEmailChange: 'email address cannot be changed in the app',
    transfer: 'Chapter V',
  }],
  ['cs', csPrivacy, {
    accessToken: '15 minut', refresh: '7 dní', reset: '60 minut',
    verify: '24 hodin', logs: 'tři dny',
    noEmailChange: 'E-mailovou adresu v aplikaci změnit nelze',
    transfer: 'kapitoly V',
  }],
] as const)('privacy notice facts, %s', (_lang, bundle, expected) => {
  const prose = JSON.stringify(bundle);

  it.each(Object.entries(expected))('states %s', (_name, phrase) => {
    expect(prose).toContain(phrase);
  });

  it('names all five processors', () => {
    for (const name of ['Railway', 'Cloudflare', 'Resend', 'Sentry', 'Better Stack']) {
      expect(prose).toContain(name);
    }
  });

  it('names the three cookies', () => {
    for (const cookie of ['__Host-access_token', '__Secure-refresh_token', '__Host-csrf_token']) {
      expect(prose).toContain(cookie);
    }
  });

  it('cites both lawful bases', () => {
    expect(prose).toMatch(/6\(1\)\(b\)|6 odst. 1 písm. b\)/);
    expect(prose).toMatch(/6\(1\)\(f\)|6 odst. 1 písm. f\)/);
  });
});
