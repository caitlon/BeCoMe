import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import Terms from '@/pages/Terms';
import enTerms from '@/i18n/locales/en/terms.json';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);
vi.mock('framer-motion', () => framerMotionMock);

describe('Terms', () => {
  it('renders the page heading and every section', () => {
    render(<Terms />);

    expect(screen.getByRole('heading', { name: 'Terms of use', level: 1 })).toBeInTheDocument();
    for (const heading of [
      'Who runs this service',
      'What a result means',
      'The assistant is an AI',
      'Rules of use',
      'Your account and your content',
      'No guarantees',
      'Which law applies',
      'Your data',
    ]) {
      expect(screen.getByRole('heading', { name: heading, level: 2 })).toBeInTheDocument();
    }
  });

  it('offers the operator mailto link', () => {
    render(<Terms />);

    expect(screen.getByRole('link', { name: 'caiton@pm.me' })).toHaveAttribute(
      'href',
      'mailto:caiton@pm.me'
    );
  });

  it('lists every rule of use', () => {
    render(<Terms />);

    expect(enTerms.rules.items.length).toBeGreaterThan(0);
    for (const item of enTerms.rules.items) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
  });

  it('says the assistant is an AI and its answers can be wrong', () => {
    render(<Terms />);

    expect(screen.getByText(/artificial intelligence system/)).toBeInTheDocument();
    expect(screen.getByText(/can be wrong, incomplete or out of date/)).toBeInTheDocument();
  });

  it('links to the privacy notice', () => {
    render(<Terms />);

    expect(screen.getByRole('link', { name: 'Read the Privacy notice' })).toHaveAttribute(
      'href',
      '/privacy'
    );
  });

  it('sets the document title', () => {
    render(<Terms />);

    expect(document.title).toContain('Terms of use');
  });
});
