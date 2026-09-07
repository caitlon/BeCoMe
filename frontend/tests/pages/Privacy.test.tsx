import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import Privacy from '@/pages/Privacy';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);
vi.mock('framer-motion', () => framerMotionMock);

describe('Privacy', () => {
  it('renders the page heading', () => {
    render(<Privacy />);

    expect(screen.getByRole('heading', { name: 'Privacy', level: 1 })).toBeInTheDocument();
  });

  it('names the controller and offers a mailto link', () => {
    render(<Privacy />);

    const link = screen.getByRole('link', { name: 'xkuze010@studenti.czu.cz' });
    expect(link).toHaveAttribute('href', 'mailto:xkuze010@studenti.czu.cz');
    expect(screen.getByText(/Ekaterina Kuzmina runs this service/)).toBeInTheDocument();
  });

  it('renders every list section with its bullets', () => {
    render(<Privacy />);

    for (const heading of [
      'What is stored',
      'Cookies',
      'Who else handles it',
      'How long',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    }
    // the six stored-data bullets, so a locale file losing one fails here
    expect(screen.getByText(/Your email address, which identifies the account/)).toBeInTheDocument();
    expect(screen.getByText(/stored only as a hash/)).toBeInTheDocument();
  });

  it('states the three cookies and why no banner is shown', () => {
    render(<Privacy />);

    expect(screen.getByText(/__Host-access_token keeps you signed in/)).toBeInTheDocument();
    expect(screen.getByText(/__Secure-refresh_token renews that session/)).toBeInTheDocument();
    expect(screen.getByText(/__Host-csrf_token protects forms/)).toBeInTheDocument();
    expect(screen.getByText(/do not require a consent banner/)).toBeInTheDocument();
  });

  /**
   * `processors` is the one list section with no closing paragraph, so it exercises the
   * other side of the conditional that renders `outro`. Without it the branch that skips
   * an absent outro is never taken.
   */
  it('omits the closing paragraph for a section that has none', () => {
    render(<Privacy />);

    const heading = screen.getByRole('heading', { name: 'Who else handles it' });
    const section = heading.parentElement as HTMLElement;
    expect(within(section).getByText(/Railway hosts the application/)).toBeInTheDocument();
    // the literal key would leak into the page if the absent-outro branch were wrong
    expect(screen.queryByText('processors.outro')).not.toBeInTheDocument();
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
