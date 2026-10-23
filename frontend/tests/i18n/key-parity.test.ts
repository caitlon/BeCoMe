import { describe, it, expect } from 'vitest';
import { resources } from '@/i18n';

const namespaces = Object.keys(resources.en) as (keyof typeof resources.en)[];

function collectKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const keys: string[] = [];

  for (const key of Object.keys(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    const value = obj[key];

    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      keys.push(...collectKeys(value as Record<string, unknown>, path));
    } else {
      keys.push(path);
    }
  }

  return keys.sort();
}

const PLURAL_SUFFIX = /^(.+)_(zero|one|two|few|many|other)$/;

// Any key that ends in a plural suffix belongs to a group, so a group that lost its `_other`
// form still shows up and fails the category check. Returns each group's base path with the
// suffixes found for it.
// A plain key that ends in a plural suffix is treated as a group too, so rename it.
function pluralGroups(keys: string[]): Map<string, string[]> {
  const groups = new Map<string, string[]>();
  for (const key of keys) {
    const match = key.match(PLURAL_SUFFIX);
    if (match) {
      groups.set(match[1], [...(groups.get(match[1]) ?? []), match[2]]);
    }
  }
  return groups;
}

// English has two plural forms and Czech four, so a plural group counts as one key.
function foldPlurals(keys: string[]): string[] {
  const folded = keys.map((key) => key.match(PLURAL_SUFFIX)?.[1] ?? key);
  return [...new Set(folded)].sort();
}

describe('i18n key parity (EN ↔ CS)', () => {
  it.each(namespaces)('%s: EN and CS have identical keys', (ns) => {
    const enKeys = foldPlurals(collectKeys(resources.en[ns] as Record<string, unknown>));
    const csKeys = foldPlurals(collectKeys(resources.cs[ns] as Record<string, unknown>));

    const missingInCs = enKeys.filter((k) => !csKeys.includes(k));
    const missingInEn = csKeys.filter((k) => !enKeys.includes(k));

    expect(missingInCs, `Keys in EN but missing in CS [${ns}]`).toEqual([]);
    expect(missingInEn, `Keys in CS but missing in EN [${ns}]`).toEqual([]);
  });

  it.each(namespaces)('%s: EN and CS have the same plural groups', (ns) => {
    const enBases = [...pluralGroups(collectKeys(resources.en[ns] as Record<string, unknown>)).keys()].sort();
    const csBases = [...pluralGroups(collectKeys(resources.cs[ns] as Record<string, unknown>)).keys()].sort();

    expect(enBases.filter((k) => !csBases.includes(k)), `Plural groups only in EN [${ns}]`).toEqual([]);
    expect(csBases.filter((k) => !enBases.includes(k)), `Plural groups only in CS [${ns}]`).toEqual([]);
  });

  it('EN and CS have the same set of namespaces', () => {
    const enNs = Object.keys(resources.en).sort();
    const csNs = Object.keys(resources.cs).sort();

    expect(enNs).toEqual(csNs);
  });

  describe.each(['en', 'cs'] as const)('plural forms (%s)', (lang) => {
    const categories = new Intl.PluralRules(lang).resolvedOptions().pluralCategories.sort();

    it.each(namespaces)('%s: no plural group shares its name with a plain key', (ns) => {
      const keys = collectKeys(resources[lang][ns] as Record<string, unknown>);
      const clashes = [...pluralGroups(keys).keys()].filter((base) => keys.includes(base));

      expect(clashes, `Keys in ${lang}/${ns} that exist both plain and as a plural group`).toEqual([]);
    });

    it.each(namespaces)('%s: every plural group has exactly the CLDR categories', (ns) => {
      const groups = pluralGroups(collectKeys(resources[lang][ns] as Record<string, unknown>));
      const wrong = [...groups].filter(([, found]) => found.sort().join() !== categories.join());

      expect(
        wrong.map(([base, found]) => `${base}: ${found.sort().join(', ')}`),
        `Plural groups in ${lang}/${ns} that do not match ${categories.join(', ')}`,
      ).toEqual([]);
    });
  });
});
