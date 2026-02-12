import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, unauthenticatedAuthMock } from '@tests/utils';
import { CaseStudyCard } from '@/components/CaseStudyCard';
import { FileText } from 'lucide-react';
import { LocalizedCaseStudy } from '@/hooks/useLocalizedCaseStudies';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);

const mockStudy: LocalizedCaseStudy = {
  id: 'budget',
  title: 'COVID-19 Budget Support',
  shortTitle: 'Budget',
  description: 'Budget allocation for pandemic response',
  fullDescription: 'Full description text',
  question: 'What budget?',
  icon: FileText,
  experts: 22,
  dataType: 'interval',
  scaleMin: 0,
  scaleMax: 100,
  scaleUnit: 'CZK billion',
  context: 'Context text',
  methodology: 'Methodology text',
  opinions: [],
  result: {
    bestCompromise: 57.3,
    maxError: 8.2,
    interpretation: 'Interpretation text',
  },
};

describe('CaseStudyCard', () => {
  it('renders study title', () => {
    render(<CaseStudyCard study={mockStudy} />);

    expect(screen.getByRole('heading', { name: /covid-19 budget support/i })).toBeInTheDocument();
  });

  it('renders study description', () => {
    render(<CaseStudyCard study={mockStudy} />);

    expect(screen.getByText('Budget allocation for pandemic response')).toBeInTheDocument();
  });

  it('links to case study page', () => {
    render(<CaseStudyCard study={mockStudy} />);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/case-study/budget');
  });

  it('displays expert count', () => {
    render(<CaseStudyCard study={mockStudy} />);

    expect(screen.getByText(/22/)).toBeInTheDocument();
  });

  it('shows scale info when showScale is true', () => {
    render(<CaseStudyCard study={mockStudy} showScale />);

    expect(screen.getByText(/0–100/)).toBeInTheDocument();
  });

  it('hides scale info by default', () => {
    render(<CaseStudyCard study={mockStudy} />);

    expect(screen.queryByText(/0–100/)).not.toBeInTheDocument();
  });

  it('marks decorative icon as aria-hidden', () => {
    const { container } = render(<CaseStudyCard study={mockStudy} />);

    // FileText icon is decorative — verify it's hidden from assistive tech
    const svgIcons = container.querySelectorAll('svg[aria-hidden="true"]');
    expect(svgIcons.length).toBeGreaterThan(0);
  });
});
