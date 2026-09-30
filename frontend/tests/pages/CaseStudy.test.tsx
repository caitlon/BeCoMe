import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import CaseStudy from '@/pages/CaseStudy';
import i18n from '@/i18n';

const { mockParams } = vi.hoisted(() => ({
  mockParams: { value: { id: 'budget' } },
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useParams: () => mockParams.value,
    useLocation: () => ({ pathname: `/case-studies/${mockParams.value.id}`, search: '', hash: '', state: null, key: 'default' }),
  };
});

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('CaseStudy - Budget', () => {
  beforeEach(() => {
    mockParams.value = { id: 'budget' };
  });

  it('renders case study title for valid ID', () => {
    render(<CaseStudy />);

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('shows "Create Account" linking to /register in the call to action', () => {
    render(<CaseStudy />);

    const cta = within(screen.getByRole('main')).getByRole('link', { name: 'Create Account' });
    expect(cta).toHaveAttribute('href', '/register');
  });

  it('renders expert count and data type', () => {
    render(<CaseStudy />);

    // The "22 experts" span uses font-mono
    expect(screen.getByText(/22\s+experts/i)).toBeInTheDocument();
    expect(screen.getByText(/interval scale/i)).toBeInTheDocument();
  });

  it('renders question in blockquote', () => {
    const { container } = render(<CaseStudy />);

    const blockquote = container.querySelector('blockquote');
    expect(blockquote).toBeInTheDocument();
    expect(blockquote?.textContent).toBeTruthy();
  });

  it('renders results card with best compromise', () => {
    render(<CaseStudy />);

    expect(screen.getByText('48.03')).toBeInTheDocument();
  });

  it('renders opinion table with expert rows', () => {
    render(<CaseStudy />);

    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();

    // Budget case has 22 experts
    const rows = table.querySelectorAll('tbody tr');
    expect(rows.length).toBe(22);
  });

  it('main content area has id="main-content"', () => {
    render(<CaseStudy />);

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main-content');
  });
});

describe('CaseStudy - Pendlers (Likert)', () => {
  beforeEach(() => {
    mockParams.value = { id: 'pendlers' };
  });

  it('renders Likert scale label instead of interval scale', () => {
    render(<CaseStudy />);

    expect(screen.getAllByText(/likert scale/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/interval scale/i)).not.toBeInTheDocument();
  });

  it('renders Likert table with Value and Label columns', () => {
    render(<CaseStudy />);

    const table = screen.getByRole('table');
    const headers = within(table).getAllByRole('columnheader');
    const headerTexts = headers.map(h => h.textContent?.trim());
    expect(headerTexts).toContain('Value');
    expect(headerTexts).toContain('Label');
  });

  it('renders LikertRow with value and localized label', () => {
    render(<CaseStudy />);

    const table = screen.getByRole('table');
    const rows = table.querySelectorAll('tbody tr');
    expect(rows.length).toBe(22);

    // First row: Chairman, value 75 => "Rather Agree" (62.5-87.5)
    expect(rows[0].textContent).toContain('Chairman');
    expect(rows[0].textContent).toContain('75');
    expect(rows[0].textContent).toContain('Rather Agree');
  });

  it('renders LikertInterpretation in results card', () => {
    render(<CaseStudy />);

    // bestCompromise = 30.68 => "Rather Disagree" (12.5-37.5)
    const interpHeading = screen.getByText(/likert interpretation/i);
    expect(interpHeading).toBeInTheDocument();
    // LikertInterpretation renders heading + label as siblings inside a wrapper div
    const interpWrapper = interpHeading.parentElement!;
    expect(interpWrapper.textContent).toContain('Rather Disagree');
  });

  it('does NOT render opinion distribution for Likert data', () => {
    render(<CaseStudy />);

    expect(screen.queryByText(/opinion distribution/i)).not.toBeInTheDocument();
  });
});

describe('CaseStudy - illustrative data note', () => {
  afterEach(() => {
    mockParams.value = { id: 'budget' };
  });

  it.each(['budget', 'pendlers'])('shows the note on the %s page', (id) => {
    mockParams.value = { id };
    render(<CaseStudy />);

    expect(screen.getByText(/illustrative fictional data/i)).toBeInTheDocument();
  });

  it('does not show the note on the floods page', () => {
    mockParams.value = { id: 'floods' };
    render(<CaseStudy />);

    expect(screen.queryByText(/illustrative fictional data/i)).not.toBeInTheDocument();
  });

  it('places the note after the description in reading order', () => {
    mockParams.value = { id: 'budget' };
    render(<CaseStudy />);

    const description = screen.getByText(/high-ranking government officials/i);
    const note = screen.getByText(/illustrative fictional data/i);
    expect(description.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it.each(['budget', 'pendlers'])('shows the Czech note on the %s page', async (id) => {
    await i18n.changeLanguage('cs');
    try {
      mockParams.value = { id };
      const { unmount } = render(<CaseStudy />);

      expect(screen.getByText(/ilustrativní fiktivní data/i)).toBeInTheDocument();

      unmount();
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('does not show the Czech note on the floods page', async () => {
    await i18n.changeLanguage('cs');
    try {
      mockParams.value = { id: 'floods' };
      const { unmount } = render(<CaseStudy />);

      expect(screen.queryByText(/ilustrativní fiktivní data/i)).not.toBeInTheDocument();

      unmount();
    } finally {
      await i18n.changeLanguage('en');
    }
  });
});

describe('CaseStudy - Opinion Distribution', () => {
  beforeEach(() => {
    mockParams.value = { id: 'budget' };
  });

  it('renders at most 8 opinion bars', () => {
    render(<CaseStudy />);

    const bars = screen.getAllByTestId('opinion-bar');
    expect(bars.length).toBe(8);
  });

  it('shows a "shown of total" count when opinions exceed the visible bar limit', () => {
    render(<CaseStudy />);

    // Budget has 22 opinions, only 8 bars are rendered
    expect(screen.getByText(/showing 8 of 22 opinions/i)).toBeInTheDocument();
  });

  it('wraps the bar chart in a figure with an sr-only figcaption', () => {
    render(<CaseStudy />);

    const figure = screen.getByRole('figure');
    const caption = figure.querySelector('figcaption');
    expect(caption).toBeInTheDocument();
    expect(caption).toHaveClass('sr-only');
    expect(caption?.textContent).toBeTruthy();
  });

  it('gives each opinion bar an sr-only description with role and range', () => {
    render(<CaseStudy />);

    const bars = screen.getAllByTestId('opinion-bar');
    // First budget opinion is the Chairman: bestProposal 70, lowerLimit 40, upperLimit 90
    const description = bars[0].querySelector('.sr-only');
    expect(description).toBeInTheDocument();
    expect(description?.textContent).toMatch(/chairman/i);
    expect(description?.textContent).toMatch(/40/);
    expect(description?.textContent).toMatch(/90/);
  });
});

describe('CaseStudy - scrollTo', () => {
  it('calls window.scrollTo on mount', () => {
    const scrollToSpy = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    mockParams.value = { id: 'budget' };

    render(<CaseStudy />);

    expect(scrollToSpy).toHaveBeenCalledWith(0, 0);
    scrollToSpy.mockRestore();
  });
});

describe('CaseStudy - document title', () => {
  afterEach(() => {
    mockParams.value = { id: 'budget' };
    document.title = '';
  });

  it('names the study in the tab title', () => {
    mockParams.value = { id: 'budget' };
    render(<CaseStudy />);

    expect(document.title).toBe('Case Study: COVID-19 Budget Support - BeCoMe');
  });

  it('gives each study its own tab title', () => {
    mockParams.value = { id: 'floods' };
    render(<CaseStudy />);
    const floodsTitle = document.title;

    mockParams.value = { id: 'pendlers' };
    render(<CaseStudy />);

    expect(document.title).not.toBe(floodsTitle);
  });

  it('uses the Czech study title in the Czech interface', async () => {
    await i18n.changeLanguage('cs');
    try {
      mockParams.value = { id: 'budget' };
      const { unmount } = render(<CaseStudy />);

      expect(document.title).toBe('Případová studie: Podpora rozpočtu COVID-19 - BeCoMe');

      unmount();
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('keeps the generic title for an unknown id', () => {
    mockParams.value = { id: 'nonexistent' };
    render(<CaseStudy />);

    expect(document.title).toBe('Case Study - BeCoMe');
  });
});

describe('CaseStudy - Not Found', () => {
  beforeEach(() => {
    mockParams.value = { id: 'nonexistent' };
  });

  it('renders not-found state for invalid ID', () => {
    render(<CaseStudy />);

    expect(screen.getByRole('heading', { level: 1, name: '404' })).toBeInTheDocument();
  });

  it('not-found state has link to /', () => {
    render(<CaseStudy />);

    const homeLink = screen.getByRole('link', { name: /back|home|zpět/i });
    expect(homeLink).toHaveAttribute('href', '/');
  });
});

describe('CaseStudy - undefined id', () => {
  beforeEach(() => {
    mockParams.value = { id: undefined } as unknown as { id: string };
  });

  afterEach(() => {
    mockParams.value = { id: 'budget' };
  });

  it('renders not found when id is undefined', () => {
    render(<CaseStudy />);
    expect(screen.getByRole('heading', { level: 1, name: '404' })).toBeInTheDocument();
  });
});
