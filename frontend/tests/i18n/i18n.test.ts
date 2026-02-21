import { describe, it, expect } from 'vitest';
import i18n, { defaultNS, resources } from '@/i18n';

const expectedNamespaces = [
  'common', 'landing', 'auth', 'about', 'projects',
  'profile', 'caseStudies', 'docs', 'onboarding', 'faq',
];

describe('i18n configuration', () => {
  it('exports defaultNS as "common"', () => {
    expect(defaultNS).toBe('common');
  });

  it('resources contain en and cs languages', () => {
    expect(Object.keys(resources)).toEqual(['en', 'cs']);
  });

  it('each language has 10 namespaces', () => {
    expect(Object.keys(resources.en)).toHaveLength(10);
    expect(Object.keys(resources.cs)).toHaveLength(10);
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
