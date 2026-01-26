import { describe, it, expect } from 'vitest';
import { getCaseStudyById, getLikertLabel, caseStudies } from '@/data/caseStudies';

describe('getCaseStudyById', () => {
  it('returns case study for valid id', () => {
    const result = getCaseStudyById('budget');
    expect(result).toBeDefined();
    expect(result?.id).toBe('budget');
  });

  it('returns undefined for invalid id', () => {
    const result = getCaseStudyById('nonexistent');
    expect(result).toBeUndefined();
  });

  it('returns undefined for empty string id', () => {
    const result = getCaseStudyById('');
    expect(result).toBeUndefined();
  });

  it('returns correct case study data', () => {
    const floods = getCaseStudyById('floods');
    expect(floods).toBeDefined();
    expect(floods?.title).toBeDefined();
    expect(floods?.experts).toBeGreaterThan(0);
  });
});

describe('getLikertLabel', () => {
  it('returns "Strongly Disagree" for values <= 12.5', () => {
    expect(getLikertLabel(0)).toBe('Strongly Disagree');
    expect(getLikertLabel(12.5)).toBe('Strongly Disagree');
    expect(getLikertLabel(5)).toBe('Strongly Disagree');
  });

  it('returns "Rather Disagree" for values > 12.5 and <= 37.5', () => {
    expect(getLikertLabel(12.6)).toBe('Rather Disagree');
    expect(getLikertLabel(25)).toBe('Rather Disagree');
    expect(getLikertLabel(37.5)).toBe('Rather Disagree');
  });

  it('returns "Neutral" for values > 37.5 and <= 62.5', () => {
    expect(getLikertLabel(37.6)).toBe('Neutral');
    expect(getLikertLabel(50)).toBe('Neutral');
    expect(getLikertLabel(62.5)).toBe('Neutral');
  });

  it('returns "Rather Agree" for values > 62.5 and <= 87.5', () => {
    expect(getLikertLabel(62.6)).toBe('Rather Agree');
    expect(getLikertLabel(75)).toBe('Rather Agree');
    expect(getLikertLabel(87.5)).toBe('Rather Agree');
  });

  it('returns "Strongly Agree" for values > 87.5', () => {
    expect(getLikertLabel(87.6)).toBe('Strongly Agree');
    expect(getLikertLabel(100)).toBe('Strongly Agree');
    expect(getLikertLabel(99)).toBe('Strongly Agree');
  });

  it('handles exact boundary values correctly', () => {
    // Test exact boundaries
    expect(getLikertLabel(12.5)).toBe('Strongly Disagree');
    expect(getLikertLabel(12.50001)).toBe('Rather Disagree');
    expect(getLikertLabel(37.5)).toBe('Rather Disagree');
    expect(getLikertLabel(37.50001)).toBe('Neutral');
    expect(getLikertLabel(62.5)).toBe('Neutral');
    expect(getLikertLabel(62.50001)).toBe('Rather Agree');
    expect(getLikertLabel(87.5)).toBe('Rather Agree');
    expect(getLikertLabel(87.50001)).toBe('Strongly Agree');
  });
});

describe('caseStudies', () => {
  it('contains expected case studies', () => {
    expect(caseStudies.length).toBeGreaterThan(0);

    const ids = caseStudies.map(cs => cs.id);
    expect(ids).toContain('budget');
    expect(ids).toContain('floods');
    expect(ids).toContain('pendlers');
  });

  it('all case studies have required fields', () => {
    caseStudies.forEach(cs => {
      expect(cs.id).toBeDefined();
      expect(cs.title).toBeDefined();
      expect(cs.experts).toBeGreaterThan(0);
      expect(cs.scaleMin).toBeDefined();
      expect(cs.scaleMax).toBeDefined();
      expect(cs.result).toBeDefined();
    });
  });
});
