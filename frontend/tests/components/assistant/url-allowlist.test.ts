import { describe, it, expect } from 'vitest';
import { isAllowedAssistantUrl } from '@/components/assistant/url-allowlist';

describe('isAllowedAssistantUrl', () => {
  it.each([
    'https://docs.becomify.app/user/reading-the-result',
    'https://example.com/page',
  ])('accepts an https url: %s', (url) => {
    expect(isAllowedAssistantUrl(url)).toBe(true);
  });

  it.each([
    'http://docs.becomify.app/user',
    'javascript:alert(1)',
    'data:text/html,<b>x</b>',
    'ftp://example.com/file',
    '/relative/path',
    'not a url',
    '',
  ])('rejects %s', (url) => {
    expect(isAllowedAssistantUrl(url)).toBe(false);
  });

  it.each([null, undefined, 42, {}, ['https://example.com']])('rejects a non-string: %s', (value) => {
    expect(isAllowedAssistantUrl(value)).toBe(false);
  });
});
