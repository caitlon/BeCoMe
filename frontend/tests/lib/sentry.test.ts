import { describe, it, expect } from 'vitest';
import type { Breadcrumb, ErrorEvent } from '@sentry/react';
import { scrubBreadcrumb, scrubEvent, scrubUrl } from '@/lib/sentry';

const RESET_TOKEN = 'live-single-use-reset-token';

describe('scrubUrl', () => {
  it('redacts a reset token on a relative URL and keeps it relative', () => {
    const result = scrubUrl(`/reset-password?token=${RESET_TOKEN}`);

    expect(result).toBe('/reset-password?token=%5Bredacted%5D');
    expect(result).not.toContain(RESET_TOKEN);
  });

  it('redacts a reset token on an absolute URL', () => {
    const result = scrubUrl(`https://app.example/reset-password?token=${RESET_TOKEN}&lang=cs`);

    expect(result).not.toContain(RESET_TOKEN);
    expect(result).toContain('lang=cs');
    expect(result.startsWith('https://app.example/reset-password')).toBe(true);
  });

  it('redacts oauth-style token parameters too', () => {
    const result = scrubUrl('/callback?access_token=a&refresh_token=b');

    expect(result).not.toContain('=a');
    expect(result).not.toContain('=b');
  });

  it('leaves a URL without sensitive parameters untouched', () => {
    const url = '/projects/42?tab=opinions';

    expect(scrubUrl(url)).toBe(url);
  });

  it('returns unparseable input unchanged rather than throwing', () => {
    // A malformed host makes the URL constructor throw; the scrubber must not be
    // the reason an event fails to send.
    const malformed = 'http://[/reset-password?token=abc';

    expect(scrubUrl(malformed)).toBe(malformed);
  });

  it('keeps a relative URL relative when nothing needs redacting', () => {
    expect(scrubUrl('://nonsense')).toBe('://nonsense');
  });
});

describe('scrubEvent', () => {
  it('redacts the token in the event request URL', () => {
    const event = {
      request: { url: `https://app.example/reset-password?token=${RESET_TOKEN}` },
    } as ErrorEvent;

    const result = scrubEvent(event);

    expect(result.request?.url).not.toContain(RESET_TOKEN);
  });

  it('passes through an event with no request URL', () => {
    const event = { message: 'boom' } as ErrorEvent;

    expect(scrubEvent(event)).toBe(event);
  });
});

describe('scrubBreadcrumb', () => {
  it('redacts navigation crumbs carrying the token', () => {
    const crumb = {
      category: 'navigation',
      data: { from: '/forgot-password', to: `/reset-password?token=${RESET_TOKEN}` },
    } as Breadcrumb;

    const result = scrubBreadcrumb(crumb);

    expect(result.data?.to).not.toContain(RESET_TOKEN);
    expect(result.data?.from).toBe('/forgot-password');
  });

  it('redacts the url of a fetch crumb', () => {
    const crumb = {
      category: 'fetch',
      data: { url: `/api/v1/auth/reset-password?token=${RESET_TOKEN}`, status_code: 400 },
    } as Breadcrumb;

    const result = scrubBreadcrumb(crumb);

    expect(result.data?.url).not.toContain(RESET_TOKEN);
    expect(result.data?.status_code).toBe(400);
  });

  it('passes through a crumb with no data', () => {
    const crumb = { category: 'ui.click' } as Breadcrumb;

    expect(scrubBreadcrumb(crumb)).toBe(crumb);
  });
});
