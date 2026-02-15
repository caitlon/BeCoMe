import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';
import CaseStudies from '@/pages/CaseStudies';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);

vi.mock('framer-motion', () => framerMotionMock);

describe('CaseStudies', () => {
  it('scrolls to top on mount', () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});

    try {
      render(<CaseStudies />);
      expect(scrollTo).toHaveBeenCalledWith(0, 0);
    } finally {
      scrollTo.mockRestore();
    }
  });

  it('renders page title', () => {
    render(<CaseStudies />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/case studies|případové studie/i);
  });

  it('renders subtitle', () => {
    render(<CaseStudies />);

    expect(screen.getByText(/real-world applications|reálné aplikace/i)).toBeInTheDocument();
  });

  it('renders three case study cards', () => {
    render(<CaseStudies />);

    const links = screen.getAllByRole('link').filter(
      (link) => link.getAttribute('href')?.startsWith('/case-study/')
    );
    expect(links).toHaveLength(3);
  });

  it('links to individual case study pages', () => {
    render(<CaseStudies />);

    const caseStudyLinks = screen.getAllByRole('link').filter(
      (link) => link.getAttribute('href')?.startsWith('/case-study/')
    );
    const hrefs = caseStudyLinks.map((link) => link.getAttribute('href'));
    expect(hrefs).toContain('/case-study/budget');
    expect(hrefs).toContain('/case-study/floods');
    expect(hrefs).toContain('/case-study/pendlers');
  });

  it('displays expert count for each study', () => {
    render(<CaseStudies />);

    // Budget and Pendlers have 22 experts, Floods has 13
    const expertTexts = screen.getAllByText(/\d+\s+expert/i);
    expect(expertTexts.length).toBe(3);
  });

  it('displays scale information', () => {
    render(<CaseStudies />);

    // Budget and Pendlers have 0–100, Floods has 0–100 too — all 3 show scale
    const scaleElements = screen.getAllByText(/0–100/);
    expect(scaleElements.length).toBeGreaterThanOrEqual(2);
  });

  it('has main content area with id', () => {
    render(<CaseStudies />);

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main-content');
  });

  it('marks decorative icons as aria-hidden', () => {
    const { container } = render(<CaseStudies />);

    const hiddenIcons = container.querySelectorAll('[aria-hidden="true"]');
    expect(hiddenIcons.length).toBeGreaterThan(0);
  });
});
