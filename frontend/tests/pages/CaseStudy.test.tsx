import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import CaseStudy from '@/pages/CaseStudy';

const { mockParams } = vi.hoisted(() => ({
  mockParams: { value: { id: 'budget' } },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
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

    expect(screen.getByText('57.3')).toBeInTheDocument();
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
    const headers = table.querySelectorAll('th');
    const headerTexts = Array.from(headers).map(h => h.textContent?.trim());
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

    // bestCompromise = 43.2 => "Neutral" (37.5-62.5)
    // "Neutral" also appears in table rows, so check for Likert Interpretation heading
    expect(screen.getByText(/likert interpretation/i)).toBeInTheDocument();
    // The LikertInterpretation component renders a label next to the heading
    const interpSection = screen.getByText(/likert interpretation/i).closest('div');
    expect(interpSection?.parentElement?.textContent).toContain('Neutral');
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
    const { container } = render(<CaseStudy />);

    // Opinion distribution bars have class "relative h-6"
    const distSection = screen.getByText(/opinion distribution/i).closest('[class*="card"]');
    const bars = distSection?.querySelectorAll('.relative.h-6');
    expect(bars?.length).toBe(8);
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

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/not found|nenalezeno/i);
  });

  it('not-found state has link to /', () => {
    render(<CaseStudy />);

    const homeLink = screen.getByRole('link', { name: /back|home|zpět/i });
    expect(homeLink).toHaveAttribute('href', '/');
  });
});

describe('CaseStudy - undefined id', () => {
  beforeEach(() => {
    mockParams.value = { id: undefined } as any;
  });

  afterEach(() => {
    mockParams.value = { id: 'budget' };
  });

  it('renders not found when id is undefined', () => {
    render(<CaseStudy />);
    expect(screen.getByText(/not found/i)).toBeInTheDocument();
  });
});
