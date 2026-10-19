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

// A key is part of a plural group only when its base also has an `_other` form, so an
// ordinary key that merely ends in `_one` is left alone. Returns each group's base path
// with the suffixes found for it.
function pluralGroups(keys: string[]): Map<string, string[]> {
  const bases = new Set(
    keys.map((k) => k.match(PLURAL_SUFFIX)).filter((m) => m?.[2] === 'other').map((m) => m![1]),
  );
  const groups = new Map<string, string[]>();
  for (const key of keys) {
    const match = key.match(PLURAL_SUFFIX);
    if (match && bases.has(match[1])) {
      groups.set(match[1], [...(groups.get(match[1]) ?? []), match[2]]);
    }
  }
  return groups;
}

// English has two plural forms and Czech four, so a plural group counts as one key.
function foldPlurals(keys: string[]): string[] {
  const groups = pluralGroups(keys);
  const folded = keys.map((key) => {
    const match = key.match(PLURAL_SUFFIX);
    return match && groups.has(match[1]) ? match[1] : key;
  });
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

  it('EN and CS have the same set of namespaces', () => {
    const enNs = Object.keys(resources.en).sort();
    const csNs = Object.keys(resources.cs).sort();

    expect(enNs).toEqual(csNs);
  });

  describe.each(['en', 'cs'] as const)('plural forms (%s)', (lang) => {
    const categories = new Intl.PluralRules(lang).resolvedOptions().pluralCategories.sort();

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
