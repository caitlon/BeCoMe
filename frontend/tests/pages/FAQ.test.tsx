import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock, unauthenticatedAuthMock, expectSectionIds, getGithubLinks } from '@tests/utils';
import FAQ from '@/pages/FAQ';
import i18n from '@/i18n';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);

vi.mock('framer-motion', () => framerMotionMock);

describe('FAQ', () => {
  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

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

  it('clicking sidebar button does not throw', async () => {
    const user = userEvent.setup();
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});

    render(<FAQ />);

    const nav = screen.getByRole('navigation', { name: /categories|kategorie/i });
    const buttons = within(nav).getAllByRole('button');

    await user.click(buttons[0]);

    expect(buttons[0]).toBeInTheDocument();

    vi.restoreAllMocks();
  });

  it('CTA section has GitHub external link', () => {
    render(<FAQ />);

    const githubLinks = getGithubLinks();
    expect(githubLinks.length).toBeGreaterThan(0);

    for (const link of githubLinks) {
      expect(link).toHaveAttribute('target', '_blank');
    }
  });

  it('renders all category sections with IDs', () => {
    const { container } = render(<FAQ />);

    expectSectionIds(container, ['method', 'fuzzyNumbers', 'results', 'application', 'troubleshooting']);
  });

  it.each([
    [
      'en',
      'What input formats are supported?',
      'One format: a fuzzy triangular number. It has three values, Lower, Peak and Upper: the lowest value you would accept, the one you consider most likely, and the highest. If you are certain, enter the same value in all three fields. A Likert scale input is not available yet.',
    ],
    [
      'cs',
      'Jaké vstupní formáty jsou podporovány?',
      'Jeden formát: fuzzy trojúhelníkové číslo. Tvoří ho tři hodnoty, Dolní, Vrchol a Horní: nejnižší hodnota, kterou byste přijali, ta, kterou považujete za nejpravděpodobnější, a nejvyšší. Pokud jste si jisti, zadejte do všech tří polí stejnou hodnotu. Zadávání na Likertově škále zatím není k dispozici.',
    ],
  ])('input formats answer describes the one triangular format (%s)', async (language, question, answer) => {
    const user = userEvent.setup();
    await i18n.changeLanguage(language);

    render(<FAQ />);
    await user.click(screen.getByRole('button', { name: question }));

    expect(screen.getByText(answer)).toBeInTheDocument();
  });
});
