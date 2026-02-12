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
    // fallbackLng can be string, array, or object
    if (Array.isArray(fallback)) {
      expect(fallback).toContain('en');
    } else {
      expect(fallback).toBe('en');
    }
  });

  it('updates document.documentElement.lang on language change', async () => {
    await i18n.changeLanguage('cs');
    expect(document.documentElement.lang).toBe('cs');

    await i18n.changeLanguage('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('uses "become-language" as localStorage key for detection', () => {
    const detection = i18n.options.detection as Record<string, unknown> | undefined;
    expect(detection?.lookupLocalStorage).toBe('become-language');
  });
});
