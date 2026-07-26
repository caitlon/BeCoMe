import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import CaseStudy from '@/pages/CaseStudy';

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

    expect(screen.getByText('56.74')).toBeInTheDocument();
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

    // bestCompromise = 41.48 => "Neutral" (37.5-62.5)
    const interpHeading = screen.getByText(/likert interpretation/i);
    expect(interpHeading).toBeInTheDocument();
    // LikertInterpretation renders heading + label as siblings inside a wrapper div
    const interpWrapper = interpHeading.parentElement!;
    expect(interpWrapper.textContent).toContain('Neutral');
  });

  it('does NOT render opinion distribution for Likert data', () => {
    render(<CaseStudy />);

    expect(screen.queryByText(/opinion distribution/i)).not.toBeInTheDocument();
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
