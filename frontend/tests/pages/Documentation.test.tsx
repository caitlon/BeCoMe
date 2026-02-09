import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import Documentation from '@/pages/Documentation';

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Documentation', () => {
  it('renders page heading', () => {
    render(<Documentation />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('TOC navigation has 5 buttons', () => {
    render(<Documentation />);

    const nav = screen.getByRole('navigation', { name: /table of contents|obsah/i });
    const buttons = within(nav).getAllByRole('button');
    expect(buttons).toHaveLength(5);
  });

  it('Getting Started section exists', () => {
    const { container } = render(<Documentation />);

    const gettingStarted = container.querySelector('#getting-started');
    expect(gettingStarted).toBeInTheDocument();
  });

  it('Glossary section exists', () => {
    const { container } = render(<Documentation />);

    const glossary = container.querySelector('#glossary');
    expect(glossary).toBeInTheDocument();
  });

  it('main content area has id="main-content"', () => {
    render(<Documentation />);

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main-content');
  });
});
