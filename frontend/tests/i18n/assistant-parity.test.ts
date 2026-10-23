import { describe, it, expect } from 'vitest';
import en from '@/i18n/locales/en/assistant.json';
import cs from '@/i18n/locales/cs/assistant.json';

// Arrays are walked by index, so the suggestion lists must match in length too.
function collectKeys(obj: object, prefix = ''): string[] {
  const keys: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'object' && value !== null) {
      keys.push(...collectKeys(value, path));
    } else {
      keys.push(path);
    }
  }
  return keys.sort();
}

function valueAt(resource: object, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, part) => (acc as Record<string, unknown>)[part], resource);
}

describe('assistant.json key parity (EN <-> CS)', () => {
  it('has identical keys in both locales', () => {
    const enKeys = collectKeys(en);
    const csKeys = collectKeys(cs);

    expect(enKeys.filter((k) => !csKeys.includes(k)), 'in EN but missing in CS').toEqual([]);
    expect(csKeys.filter((k) => !enKeys.includes(k)), 'in CS but missing in EN').toEqual([]);
  });

  it('has a non-empty string behind every key', () => {
    for (const [locale, resource] of [['en', en], ['cs', cs]] as const) {
      for (const key of collectKeys(resource)) {
        const value = valueAt(resource, key);
        expect(typeof value, `${locale}:${key}`).toBe('string');
        expect((value as string).length, `${locale}:${key}`).toBeGreaterThan(0);
      }
    }
  });

  it('keeps the same interpolation placeholders in both locales', () => {
    for (const key of collectKeys(en)) {
      const placeholders = (text: unknown) => String(text).match(/{{\w+}}/g)?.sort() ?? [];
      expect(placeholders(valueAt(cs, key)), key).toEqual(placeholders(valueAt(en, key)));
    }
  });
});
