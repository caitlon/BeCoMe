import { describe, it, expect, vi, afterEach } from 'vitest';
import i18n, { defaultNS, resources } from '@/i18n';

const expectedNamespaces: (keyof typeof resources.en)[] = [
  'common', 'landing', 'auth', 'about', 'projects',
  'profile', 'caseStudies', 'docs', 'onboarding', 'faq',
  'privacy',
];

describe('i18n configuration', () => {
  it('exports defaultNS as "common"', () => {
    expect(defaultNS).toBe('common');
  });

  it('resources contain en and cs languages', () => {
    expect(Object.keys(resources)).toEqual(['en', 'cs']);
  });

  it('each language has 11 namespaces', () => {
    expect(Object.keys(resources.en)).toHaveLength(11);
    expect(Object.keys(resources.cs)).toHaveLength(11);
  });

  it('all namespaces are non-empty objects', () => {
    for (const ns of expectedNamespaces) {
      expect(resources.en[ns]).toBeDefined();
      expect(Object.keys(resources.en[ns]).length).toBeGreaterThan(0);
      expect(resources.cs[ns]).toBeDefined();
      expect(Object.keys(resources.cs[ns]).length).toBeGreaterThan(0);
    }
  });

  it('fallbackLng includes "en"', () => {
    const fallback = i18n.options.fallbackLng;
    if (Array.isArray(fallback)) {
      expect(fallback).toContain('en');
    } else if (typeof fallback === 'object' && fallback !== null) {
      const values = Object.values(fallback).flat();
      expect(values).toContain('en');
    } else {
      expect(fallback).toBe('en');
    }
  });

  it('updates document.documentElement.lang on language change', async () => {
    const originalLang = i18n.language;
    try {
      await i18n.changeLanguage('cs');
      expect(document.documentElement.lang).toBe('cs');

      await i18n.changeLanguage('en');
      expect(document.documentElement.lang).toBe('en');
    } finally {
      await i18n.changeLanguage(originalLang);
    }
  });

  it('uses "become-language" as localStorage key for detection', () => {
    const detection = i18n.options.detection as Record<string, unknown> | undefined;
    expect(detection?.lookupLocalStorage).toBe('become-language');
  });

  it('detection order starts with localStorage', () => {
    const detection = i18n.options.detection as Record<string, unknown> | undefined;
    const order = detection?.order as string[] | undefined;
    expect(order?.[0]).toBe('localStorage');
  });

  it('caches language preference to localStorage', () => {
    const detection = i18n.options.detection as Record<string, unknown> | undefined;
    const caches = detection?.caches as string[] | undefined;
    expect(caches).toContain('localStorage');
  });

  it('sets document.documentElement.lang on initial load', () => {
    expect(document.documentElement.lang).toBe(i18n.language);
  });

  it('has escapeValue disabled in interpolation config', () => {
    expect(i18n.options.interpolation?.escapeValue).toBe(false);
  });
});

describe('skip link text', () => {
  const SKIP_LINK_ID = 'test-skip-link';

  function addSkipLink() {
    const link = document.createElement('a');
    link.className = 'skip-to-content';
    link.id = SKIP_LINK_ID;
    link.textContent = 'Skip to main content';
    document.body.appendChild(link);
    return link;
  }

  afterEach(() => {
    document.getElementById(SKIP_LINK_ID)?.remove();
    localStorage.removeItem('become-language');
  });

  it('follows the interface language on language change', async () => {
    const link = addSkipLink();
    try {
      await i18n.changeLanguage('cs');
      expect(link.textContent).toBe('Přejít k hlavnímu obsahu');

      await i18n.changeLanguage('en');
      expect(link.textContent).toBe('Skip to main content');
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('is translated at start-up, before any language change', async () => {
    const link = addSkipLink();
    localStorage.setItem('become-language', 'cs');
    // vi.resetModules() does not reset i18next itself (it lives in node_modules), so the
    // re-import initialises the same singleton and the first import's listener would
    // update the link too. Drop the listeners so only the fresh module's own start-up
    // call, which runs once per import, can translate it.
    i18n.off('languageChanged');
    vi.resetModules();

    await import('@/i18n');

    expect(link.textContent).toBe('Přejít k hlavnímu obsahu');
  });
});
