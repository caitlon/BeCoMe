import { describe, it, expect, beforeEach, afterAll } from 'vitest';
import i18n from '@/i18n';
import { registerAssistantI18n } from '@/components/assistant/i18n';

describe('registerAssistantI18n', () => {
  beforeEach(() => {
    i18n.removeResourceBundle('en', 'assistant');
    i18n.removeResourceBundle('cs', 'assistant');
  });

  afterAll(() => {
    registerAssistantI18n();
  });

  it('adds the assistant namespace for both locales', () => {
    expect(i18n.hasResourceBundle('en', 'assistant')).toBe(false);
    expect(i18n.hasResourceBundle('cs', 'assistant')).toBe(false);

    registerAssistantI18n();

    expect(i18n.hasResourceBundle('en', 'assistant')).toBe(true);
    expect(i18n.hasResourceBundle('cs', 'assistant')).toBe(true);
    expect(i18n.getResource('en', 'assistant', 'trigger.header')).toBe('Assistant');
    expect(i18n.getResource('cs', 'assistant', 'trigger.header')).toBe('Asistent');
  });

  it('is idempotent and leaves bundles that are already there alone', () => {
    i18n.addResourceBundle('en', 'assistant', { trigger: { header: 'kept' } });

    registerAssistantI18n();
    registerAssistantI18n();

    expect(i18n.getResource('en', 'assistant', 'trigger.header')).toBe('kept');
    expect(i18n.hasResourceBundle('cs', 'assistant')).toBe(true);
  });

  it('does not overwrite a Czech bundle that is already there', () => {
    i18n.addResourceBundle('cs', 'assistant', { trigger: { header: 'kept' } });

    registerAssistantI18n();

    expect(i18n.getResource('cs', 'assistant', 'trigger.header')).toBe('kept');
    expect(i18n.hasResourceBundle('en', 'assistant')).toBe(true);
  });
});
