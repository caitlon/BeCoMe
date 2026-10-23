import { describe, it, expect } from 'vitest';
import {
  cleanChecks,
  cleanSources,
  cleanToolsUsed,
  sourceAnchorId,
} from '@/components/assistant/message-shape';

const good = {
  n: 1,
  title: 'Reading the result',
  section: 'Confidence',
  snippet: 'Quote',
  url: 'https://docs.becomify.app/user/reading-the-result',
  layer: 'public',
};

describe('sourceAnchorId', () => {
  it('names the row after the message and the source number', () => {
    expect(sourceAnchorId('m1', 3)).toBe('assistant-src-m1-3');
  });
});

describe('cleanSources', () => {
  it('keeps a well-formed source as it is', () => {
    expect(cleanSources([good])).toEqual([good]);
  });

  it('keeps a local source with a null url', () => {
    const local = { ...good, n: 2, url: null, layer: 'local' };

    expect(cleanSources([local])).toEqual([local]);
  });

  it('treats a missing snippet as empty', () => {
    const older: Record<string, unknown> = { ...good };
    delete older.snippet;

    expect(cleanSources([older])).toEqual([{ ...good, snippet: '' }]);
  });

  it.each([
    ['not an array', 'nope'],
    ['null', null],
    ['an object', { 0: good }],
  ])('returns nothing for %s', (_label, value) => {
    expect(cleanSources(value)).toEqual([]);
  });

  it.each([
    ['null entry', null],
    ['string entry', 'x'],
    ['array entry', [good]],
    ['n as a string', { ...good, n: '1' }],
    ['n zero', { ...good, n: 0 }],
    ['n negative', { ...good, n: -2 }],
    ['n fractional', { ...good, n: 1.5 }],
    ['n beyond the safe integers', { ...good, n: 1e21 }],
    ['n NaN', { ...good, n: Number.NaN }],
    ['missing title', { ...good, title: undefined }],
    ['numeric section', { ...good, section: 4 }],
    ['unknown layer', { ...good, layer: 'evil' }],
    ['numeric url', { ...good, url: 5 }],
    ['undefined url', { ...good, url: undefined }],
  ])('drops an entry with %s', (_label, entry) => {
    expect(cleanSources([entry, { ...good, n: 9 }])).toEqual([{ ...good, n: 9 }]);
  });

  it('drops a second source with a number already taken', () => {
    const second = { ...good, title: 'Second' };

    expect(cleanSources([good, second])).toEqual([good]);
  });
});

describe('cleanToolsUsed', () => {
  it('keeps string names only', () => {
    expect(cleanToolsUsed(['search_docs', 3, null, 'get_project'])).toEqual(['search_docs', 'get_project']);
  });

  it.each([undefined, null, 'search_docs', 7, {}])('returns nothing for %s', (value) => {
    expect(cleanToolsUsed(value)).toEqual([]);
  });
});

describe('cleanChecks', () => {
  it('keeps complete checks and the string numbers', () => {
    expect(
      cleanChecks({ citations_valid: false, numbers_grounded: false, ungrounded_numbers: ['17', 4, '9'] })
    ).toEqual({ citations_valid: false, numbers_grounded: false, ungrounded_numbers: ['17', '9'] });
  });

  it.each([
    ['undefined', undefined],
    ['an array', []],
    ['string flags', { citations_valid: 'true', numbers_grounded: 'false', ungrounded_numbers: [] }],
    ['one flag missing', { numbers_grounded: true, ungrounded_numbers: [] }],
    ['the other flag missing', { citations_valid: true, ungrounded_numbers: [] }],
    ['numbers not an array', { citations_valid: true, numbers_grounded: true, ungrounded_numbers: '17' }],
    ['numbers missing', { citations_valid: true, numbers_grounded: true }],
  ])('ignores checks with %s', (_label, value) => {
    expect(cleanChecks(value)).toBeNull();
  });
});
