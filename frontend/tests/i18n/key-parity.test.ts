import { describe, it, expect } from 'vitest';
import { resources } from '@/i18n';

const namespaces = Object.keys(resources.en);

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

describe('i18n key parity (EN ↔ CS)', () => {
  it.each(namespaces)('%s — EN and CS have identical keys', (ns) => {
    const enKeys = collectKeys(resources.en[ns] as Record<string, unknown>);
    const csKeys = collectKeys(resources.cs[ns] as Record<string, unknown>);

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
});
