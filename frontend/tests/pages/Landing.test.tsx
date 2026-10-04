import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import Landing from '@/pages/Landing';
import i18n from '@/i18n';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);
vi.mock('framer-motion', () => framerMotionMock);

describe('Landing', () => {
  it('renders hero section with title', () => {
    render(<Landing />);

    expect(screen.getByText('Many expert opinions,')).toBeInTheDocument();
    expect(screen.getByText('one best compromise')).toBeInTheDocument();
  });

  it('renders hero subtitle', () => {
    render(<Landing />);

    expect(
      screen.getByText(
        'For panels that must settle on one number, such as a budget, a deadline or a risk level. Each expert gives a lowest, most likely and highest estimate, and BeCoMe combines them into the best compromise.'
      )
    ).toBeInTheDocument();
  });

  it('labels every sign-up link "Create Account" for unauthenticated users', () => {
    render(<Landing />);

    // Navigation bar, hero, call to action and footer all lead to the same page
    const signUpLinks = screen.getAllByRole('link', { name: 'Create Account' });
    expect(signUpLinks).toHaveLength(4);
    signUpLinks.forEach((link) => expect(link).toHaveAttribute('href', '/register'));
  });

  it('renders "How It Works" section', () => {
    render(<Landing />);

    expect(screen.getByText('How It Works')).toBeInTheDocument();
    expect(screen.getByText('Collect')).toBeInTheDocument();
    expect(screen.getByText('Calculate')).toBeInTheDocument();
    expect(screen.getByText('Compromise')).toBeInTheDocument();
    expect(
      screen.getByText('A three-step process from expert opinions to the best compromise')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Get the best compromise and its maximum error')
    ).toBeInTheDocument();
  });

  it('renders "Case Studies" section', () => {
    render(<Landing />);

    // "Case Studies" appears multiple times (heading and navbar link)
    const caseStudiesElements = screen.getAllByText('Case Studies');
    expect(caseStudiesElements.length).toBeGreaterThan(0);
  });

  it('renders CTA section', () => {
    render(<Landing />);

    expect(screen.getByText('Ready to find the best compromise?')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Create your first project and start collecting expert opinions today. Free for noncommercial use.'
      )
    ).toBeInTheDocument();
    // Hero and call to action inside the page content
    const signUpLinks = within(screen.getByRole('main')).getAllByRole('link', {
      name: 'Create Account',
    });
    expect(signUpLinks).toHaveLength(2);
  });

  it('has link to about page', () => {
    render(<Landing />);

    const learnMoreLink = screen.getByText(/learn more about the become method/i);
    expect(learnMoreLink).toHaveAttribute('href', '/about');
  });
});

describe('Landing - Czech', () => {
  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('renders the hero headline, subtitle and third step in Czech', async () => {
    await i18n.changeLanguage('cs');
    render(<Landing />);

    expect(screen.getByText('Mnoho názorů expertů,')).toBeInTheDocument();
    expect(screen.getByText('jeden nejlepší kompromis')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Pro skupiny, které se musí shodnout na jednom čísle, například na rozpočtu, termínu nebo míře rizika. Každý expert zadá nejnižší, nejpravděpodobnější a nejvyšší odhad a BeCoMe z nich spočítá nejlepší kompromis.'
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText('Získejte nejlepší kompromis a maximální chybu')
    ).toBeInTheDocument();
  });

  it('calls the result a compromise in the steps and the call to action', async () => {
    await i18n.changeLanguage('cs');
    render(<Landing />);

    expect(screen.getByText('Kompromis')).toBeInTheDocument();
    expect(
      screen.getByText('Třístupňový proces od názorů expertů k nejlepšímu kompromisu')
    ).toBeInTheDocument();
    expect(screen.getByText('Připraveni najít nejlepší kompromis?')).toBeInTheDocument();
  });

  it('labels every sign-up link "Vytvořit účet" and states the licence condition', async () => {
    await i18n.changeLanguage('cs');
    render(<Landing />);

    const signUpLinks = screen.getAllByRole('link', { name: 'Vytvořit účet' });
    expect(signUpLinks).toHaveLength(4);
    signUpLinks.forEach((link) => expect(link).toHaveAttribute('href', '/register'));
    expect(
      screen.getByText(
        'Vytvořte svůj první projekt a začněte sbírat názory expertů ještě dnes. Pro nekomerční použití zdarma.'
      )
    ).toBeInTheDocument();
  });
});

describe('Landing - hash scrolling', () => {
  it('scrolls to element when URL has hash', () => {
    const mockScrollIntoView = vi.fn();
    const mockElement = document.createElement('div');
    mockElement.scrollIntoView = mockScrollIntoView;

    vi.spyOn(document, 'getElementById').mockReturnValue(mockElement);
    vi.useFakeTimers();

    render(<Landing />, { initialEntries: ['/#case-studies'] });

    vi.advanceTimersByTime(200);

    expect(mockScrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'center',
    });

    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('does nothing when hash element does not exist', () => {
    vi.useFakeTimers();
    vi.spyOn(document, 'getElementById').mockReturnValue(null);

    render(<Landing />, { initialEntries: ['/#nonexistent'] });

    vi.advanceTimersByTime(200);

    vi.useRealTimers();
    vi.restoreAllMocks();
  });
});
