import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';
import {
  useLocalizedCaseStudies,
  useLocalizedCaseStudyById,
  useLocalizedLikertLabel,
} from '@/hooks/useLocalizedCaseStudies';

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
);

describe('useLocalizedCaseStudies', () => {
  it('returns all case studies with localized fields', () => {
    const { result } = renderHook(() => useLocalizedCaseStudies(), { wrapper });

    expect(result.current.length).toBeGreaterThanOrEqual(3);

    for (const study of result.current) {
      expect(study.title).toBeTruthy();
      expect(study.description).toBeTruthy();
      expect(study.question).toBeTruthy();
    }
  });

  it('localized fields are non-empty strings', () => {
    const { result } = renderHook(() => useLocalizedCaseStudies(), { wrapper });

    const budget = result.current.find((s) => s.id === 'budget');
    expect(budget).toBeDefined();
    expect(typeof budget!.title).toBe('string');
    expect(budget!.title.length).toBeGreaterThan(0);
    expect(typeof budget!.description).toBe('string');
    expect(budget!.description.length).toBeGreaterThan(0);
  });
});

describe('useLocalizedCaseStudyById', () => {
  it('returns study for valid id "budget"', () => {
    const { result } = renderHook(() => useLocalizedCaseStudyById('budget'), { wrapper });

    expect(result.current).toBeDefined();
    expect(result.current!.id).toBe('budget');
    expect(result.current!.experts).toBe(22);
  });

  it('returns undefined for nonexistent id', () => {
    const { result } = renderHook(() => useLocalizedCaseStudyById('nonexistent'), { wrapper });

    expect(result.current).toBeUndefined();
  });
});

describe('useLocalizedLikertLabel', () => {
  it('returns correct labels for different values', () => {
    // 0-12.5 → Strongly Disagree
    const { result: r1 } = renderHook(() => useLocalizedLikertLabel(5), { wrapper });
    expect(r1.current).toBeTruthy();

    // 12.5-37.5 → Rather Disagree
    const { result: r2 } = renderHook(() => useLocalizedLikertLabel(25), { wrapper });
    expect(r2.current).toBeTruthy();
    expect(r2.current).not.toBe(r1.current);

    // 37.5-62.5 → Neutral
    const { result: r3 } = renderHook(() => useLocalizedLikertLabel(50), { wrapper });
    expect(r3.current).toBeTruthy();
    expect(r3.current).not.toBe(r2.current);

    // 62.5-87.5 → Rather Agree
    const { result: r4 } = renderHook(() => useLocalizedLikertLabel(75), { wrapper });
    expect(r4.current).toBeTruthy();

    // 87.5-100 → Strongly Agree
    const { result: r5 } = renderHook(() => useLocalizedLikertLabel(100), { wrapper });
    expect(r5.current).toBeTruthy();
    expect(r5.current).not.toBe(r4.current);
  });
});
