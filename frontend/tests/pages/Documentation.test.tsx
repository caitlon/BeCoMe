import { afterEach, describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock, unauthenticatedAuthMock, expectSectionIds, getGithubLinks } from '@tests/utils';
import Documentation from '@/pages/Documentation';
import i18n from '@/i18n';

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

    expectSectionIds(container, ['getting-started', 'expert-opinions', 'results', 'visualization', 'glossary']);
  });

  it('renders GitHub link in CTA section', () => {
    render(<Documentation />);

    expect(getGithubLinks().length).toBeGreaterThan(0);
  });

  describe('input format wording', () => {
    afterEach(async () => {
      await i18n.changeLanguage('en');
    });

    it.each([
      {
        lang: 'en',
        texts: [
          'Experts answer the raised question by assessing a quantitative parameter. The form takes one input format, a fuzzy triangular number, and it covers three kinds of answer:',
          'A triangular membership function with three values representing uncertainty. This is the general form of an answer.',
          'For agreement/disagreement questions on a 0 to 100 scale, turn your position into numbers with this mapping. There is no separate Likert input yet, so you enter the numbers yourself:',
        ],
      },
      {
        lang: 'cs',
        texts: [
          'Experti odpovídají na položenou otázku hodnocením kvantitativního parametru. Formulář má jeden vstupní formát, fuzzy trojúhelníkové číslo, a ten pokrývá tři druhy odpovědí:',
          'Trojúhelníková funkce příslušnosti se třemi hodnotami představujícími nejistotu. Toto je obecný tvar odpovědi.',
          'Pro otázky souhlasu/nesouhlasu na škále 0 až 100 převeďte svůj postoj na čísla podle tohoto mapování. Samostatný vstup pro Likertovu škálu zatím není, čísla proto zadáváte ručně:',
        ],
      },
    ])('describes the one input format in $lang', async ({ lang, texts }) => {
      await i18n.changeLanguage(lang);

      render(<Documentation />);

      for (const text of texts) {
        expect(screen.getByText(text)).toBeInTheDocument();
      }
    });
  });
});
