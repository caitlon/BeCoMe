import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, screen } from '@testing-library/react';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import i18n from '@/i18n';
import About from '@/pages/About';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);
vi.mock('framer-motion', () => framerMotionMock);

describe('About', () => {
  it('renders page title', () => {
    render(<About />);

    expect(screen.getByText('About BeCoMe')).toBeInTheDocument();
  });

  it('renders hero subtitle', () => {
    render(<About />);

    expect(
      screen.getByText(/best compromise mean: a scientific method/i)
    ).toBeInTheDocument();
  });

  it('renders "The Challenge" section', () => {
    render(<About />);

    expect(screen.getByText('The Challenge')).toBeInTheDocument();
  });

  it('renders "The BeCoMe Method" section', () => {
    render(<About />);

    expect(screen.getByText('The BeCoMe Method')).toBeInTheDocument();
  });

  it('renders "Applications" section with list items', () => {
    render(<About />);

    expect(screen.getByText('Applications')).toBeInTheDocument();
    expect(screen.getByText('State security decisions')).toBeInTheDocument();
    expect(screen.getByText('Public health policy')).toBeInTheDocument();
    expect(screen.getByText('Flood prevention')).toBeInTheDocument();
  });

  it('renders "Authors" section with names', () => {
    render(<About />);

    expect(screen.getByText('Authors of the method')).toBeInTheDocument();
    // Authors appear in multiple places (navbar and content), use getAllByText
    const vranaNames = screen.getAllByText('Prof. Ing. Ivan Vrana, DrSc.');
    expect(vranaNames.length).toBeGreaterThan(0);
    const tyrychtrNames = screen.getAllByText('doc. Ing. Jan Tyrychtr, Ph.D.');
    expect(tyrychtrNames.length).toBeGreaterThan(0);
    const pelikanNames = screen.getAllByText('doc. Ing. Martin Pelikán, Ph.D.');
    expect(pelikanNames.length).toBeGreaterThan(0);
  });

  it('has link to documentation', () => {
    render(<About />);

    const docsLink = screen.getByRole('link', { name: /view documentation/i });
    expect(docsLink).toHaveAttribute('href', '/docs');
  });

  it('has link to register page', () => {
    render(<About />);

    const registerLink = screen.getByRole('link', { name: /start your project/i });
    expect(registerLink).toHaveAttribute('href', '/register');
  });

  it('has link to case studies', () => {
    render(<About />);

    const caseStudiesLink = screen.getByRole('link', { name: /view case studies/i });
    expect(caseStudiesLink).toHaveAttribute('href', '/case-studies');
  });
});

describe.each([
  {
    language: 'en',
    methodParagraph:
      /BeCoMe is a simplified successor of the MaxAgM method\. MaxAgM finds the best agreement by minimizing entropy, which is complex to compute and needs specialized software\. BeCoMe needs neither: each expert's opinion is a fuzzy triangular number, and the best compromise is the midpoint between the arithmetic mean and the median of all opinions\. The method also gives the maximum error of that result, which is half the distance between the mean and the median\./,
    authorsTitle: 'Authors of the method',
    builtBy:
      'Ekaterina Kuzmina built this web application as an independent implementation of the method.',
  },
  {
    language: 'cs',
    methodParagraph:
      /BeCoMe je zjednodušený nástupce metody MaxAgM\. MaxAgM hledá nejlepší shodu minimalizací entropie, což je výpočetně náročné a vyžaduje specializovaný software\. BeCoMe se bez toho obejde: názor každého experta je fuzzy trojúhelníkové číslo a nejlepší kompromis leží uprostřed mezi aritmetickým průměrem a mediánem všech názorů\. Metoda zároveň udává maximální chybu výsledku, tedy polovinu vzdálenosti mezi průměrem a mediánem\./,
    authorsTitle: 'Autoři metody',
    builtBy:
      'Tuto webovou aplikaci jako nezávislou implementaci metody vytvořila Ekaterina Kuzmina.',
  },
])('About method and authors ($language)', ({
  language,
  methodParagraph,
  authorsTitle,
  builtBy,
}) => {
  const citation =
    'Vrana, I., Tyrychtr, J., Pelikán, M. (2021). BeCoMe: Easy-to-implement optimized method for best-compromise group decision making: Flood-prevention and COVID-19 case studies. Environmental Modelling & Software, 136, 104953. https://doi.org/10.1016/j.envsoft.2020.104953';

  beforeEach(async () => {
    await act(async () => {
      await i18n.changeLanguage(language);
    });
  });

  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  it('describes BeCoMe as the simplified successor of MaxAgM', () => {
    render(<About />);

    expect(screen.getByText(methodParagraph)).toBeInTheDocument();
  });

  it('titles the authors block', () => {
    render(<About />);

    // Only the Czech footer repeats this heading (English says "Method Authors"), so pin the h2
    expect(
      screen.getByRole('heading', { level: 2, name: authorsTitle })
    ).toBeInTheDocument();
  });

  it('cites the published paper', () => {
    render(<About />);

    expect(screen.getByText(citation, { exact: false })).toBeInTheDocument();
  });

  it('says who built the application', () => {
    render(<About />);

    expect(screen.getByText(builtBy)).toBeInTheDocument();
  });
});
