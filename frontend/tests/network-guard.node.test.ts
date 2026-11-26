// @vitest-environment node
import { describe, it, expect, vi } from 'vitest';
import { takeBlockedRequests } from '@tests/support/network-guard';

// The server-render tests run in the node environment, where fetch and WebSocket are Node's own
// and there is no XMLHttpRequest or window. The setup file guards them all the same.

describe('the network guard in the node environment', () => {
  it('has no window and no XMLHttpRequest to guard', () => {
    expect(typeof window).toBe('undefined');
    expect(typeof XMLHttpRequest).toBe('undefined');
  });

  it('refuses fetch with the URL in the message and records it', async () => {
    await expect(fetch('https://example.test/node-fetch')).rejects.toThrow(
      /Unmocked network request: fetch https:\/\/example\.test\/node-fetch/
    );

    expect(takeBlockedRequests()).toEqual([
      { api: 'fetch', url: 'https://example.test/node-fetch' },
    ]);
  });

  it('refuses a WebSocket and keeps its state constants', () => {
    expect(() => new WebSocket('wss://example.test/node-socket')).toThrow('node-socket');
    expect(WebSocket.OPEN).toBe(1);

    expect(takeBlockedRequests()).toEqual([
      { api: 'WebSocket', url: 'wss://example.test/node-socket' },
    ]);
  });

  it('is replaced by vi.stubGlobal and comes back after vi.unstubAllGlobals()', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('ok')));
    expect(await (await fetch('https://example.test/mocked')).text()).toBe('ok');

    vi.unstubAllGlobals();

    await expect(fetch('https://example.test/back')).rejects.toThrow('back');
    expect(takeBlockedRequests()).toHaveLength(1);
  });

  // The hook in tests/setup.ts fails a test that made a request and swallowed the refusal, so
  // only that hook can fail this one.
  it.fails('fails the test that swallowed a refusal, through the afterEach in tests/setup.ts', async () => {
    await fetch('https://example.test/swallowed').catch(() => undefined);
  });
});
