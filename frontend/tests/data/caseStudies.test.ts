import { describe, it, expect } from 'vitest';
import { caseStudies } from '@/data/caseStudies';

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
