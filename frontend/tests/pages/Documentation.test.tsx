import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import Documentation from '@/pages/Documentation';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);

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

  it('clicking TOC button does not throw', async () => {
    const user = userEvent.setup();
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});

    render(<Documentation />);

    const nav = screen.getByRole('navigation', { name: /table of contents|obsah/i });
    const buttons = within(nav).getAllByRole('button');

    await user.click(buttons[0]);

    expect(buttons[0]).toBeInTheDocument();

    vi.restoreAllMocks();
  });

  it('renders all expected section IDs', () => {
    const { container } = render(<Documentation />);

    const expectedIds = ['getting-started', 'expert-opinions', 'results', 'visualization', 'glossary'];
    for (const id of expectedIds) {
      expect(container.querySelector(`#${id}`)).toBeInTheDocument();
    }
  });

  it('renders GitHub link in CTA section', () => {
    render(<Documentation />);

    const githubLinks = screen.getAllByRole('link').filter(
      (link) => link.getAttribute('href')?.includes('github.com')
    );
    expect(githubLinks.length).toBeGreaterThan(0);
  });
});
