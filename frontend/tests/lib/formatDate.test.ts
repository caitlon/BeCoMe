import { describe, it, expect } from 'vitest';
import { formatDate } from '@/lib/formatDate';

describe('formatDate', () => {
  it('formats an ISO date string for the English locale with a spelled-out month', () => {
    expect(formatDate('2026-07-18T12:00:00Z', 'en')).toBe('Jul 18, 2026');
  });

  it('formats a Date instance the same way as the equivalent ISO string', () => {
    expect(formatDate(new Date('2026-07-18T12:00:00Z'), 'en')).toBe('Jul 18, 2026');
  });

  it('never renders an all-numeric, locale-ambiguous date for en', () => {
    // This is the AUD-031 bug: plain numeric formatting reads as DD/MM in
    // one place and MM/DD in another depending on how the locale is passed.
    const result = formatDate('2026-07-18T12:00:00Z', 'en');
    expect(result).not.toMatch(/^\d{1,2}\/\d{1,2}\/\d{4}$/);
  });

  it('localizes for cs using Czech day-month-year order', () => {
    expect(formatDate('2026-07-18T12:00:00Z', 'cs')).toBe('18. 7. 2026');
  });

  it('renders single-digit days and months without leading zeros', () => {
    expect(formatDate('2026-01-05T12:00:00Z', 'en')).toBe('Jan 5, 2026');
    expect(formatDate('2026-01-05T12:00:00Z', 'cs')).toBe('5. 1. 2026');
  });
});
