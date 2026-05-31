import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { logger } from '@/lib/logger';

describe('logger', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('logs debug in development', () => {
    vi.stubEnv('DEV', true);
    const spy = vi.spyOn(console, 'debug').mockImplementation(() => {});

    logger.debug('loading');

    expect(spy).toHaveBeenCalled();
  });

  it('suppresses debug in production', () => {
    vi.stubEnv('DEV', false);
    const spy = vi.spyOn(console, 'debug').mockImplementation(() => {});

    logger.debug('loading');

    expect(spy).not.toHaveBeenCalled();
  });

  it('suppresses info in production', () => {
    vi.stubEnv('DEV', false);
    const spy = vi.spyOn(console, 'info').mockImplementation(() => {});

    logger.info('done');

    expect(spy).not.toHaveBeenCalled();
  });

  it('always logs warnings', () => {
    vi.stubEnv('DEV', false);
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    logger.warn('careful');

    expect(spy).toHaveBeenCalled();
  });

  it('always logs errors', () => {
    vi.stubEnv('DEV', false);
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    logger.error('boom');

    expect(spy).toHaveBeenCalled();
  });

  it('passes context through to the console', () => {
    vi.stubEnv('DEV', false);
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    logger.error('request failed', { status: 500 });

    expect(spy).toHaveBeenCalledWith(expect.stringContaining('request failed'), { status: 500 });
  });
});
