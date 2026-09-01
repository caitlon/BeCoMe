import { describe, it, expect } from 'vitest';
import i18n, { resources } from '@/i18n';

/**
 * Regression guard for AUD-004: a component called `t("aria.loading")`, a
 * key that does not exist (the real key is `a11y.loading`). i18next's
 * missing-key fallback returns the key string unchanged, so the screen
 * reader read the literal text "aria.loading" instead of "Loading".
 *
 * Every key below is one actually passed to `t()`/`tCommon()` for an
 * aria-label, role name, or sr-only string somewhere in the app. Resolving
 * to something other than the key itself proves the key exists in both
 * locales. It would have caught the aria.loading typo immediately.
 */
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

const a11yKeys = collectKeys(resources.en.common.a11y as Record<string, unknown>).map(
  (key) => `a11y.${key}`
);

// Aria-label-bound keys that live outside the a11y.* block.
const otherCriticalAriaKeys = [
  'password.show',
  'password.hide',
  'switchToLanguage',
  'theme.toggle',
  'theme.switchToDark',
  'theme.switchToLight',
];

const criticalAriaKeys = [...a11yKeys, ...otherCriticalAriaKeys];

describe('critical aria strings resolve to real translations', () => {
  it.each(criticalAriaKeys)('%s resolves in English', (key) => {
    const t = i18n.getFixedT('en', 'common');
    expect(t(key)).not.toBe(key);
  });

  it.each(criticalAriaKeys)('%s resolves in Czech', (key) => {
    const t = i18n.getFixedT('cs', 'common');
    expect(t(key)).not.toBe(key);
  });

  it('demonstrates the historical aria.loading typo would have failed this check', () => {
    const t = i18n.getFixedT('en', 'common');
    expect(t('aria.loading')).toBe('aria.loading');
  });
});
