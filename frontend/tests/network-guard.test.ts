import { describe, it, expect, vi } from 'vitest';
import {
  failOnBlockedRequests,
  installNetworkGuard,
  takeBlockedRequests,
} from '@tests/support/network-guard';

// A refusal is recorded so that a test fails even when the code under test swallows it.
// Every test here that triggers the guard on purpose clears the record itself, with
// takeBlockedRequests(), or the setup's afterEach would fail it.

describe('fetch', () => {
  it('is refused with the URL in the message and recorded', async () => {
    await expect(fetch('https://example.test/api/things')).rejects.toThrow(
      /Unmocked network request: fetch https:\/\/example\.test\/api\/things.*vi\.stubGlobal/
    );

    expect(takeBlockedRequests()).toEqual([
      { api: 'fetch', url: 'https://example.test/api/things' },
    ]);
  });

  it('names the URL of a URL object and of a Request', async () => {
    await expect(fetch(new URL('https://example.test/a'))).rejects.toThrow('https://example.test/a');
    await expect(fetch(new Request('https://example.test/b'))).rejects.toThrow(
      'https://example.test/b'
    );

    expect(takeBlockedRequests().map((blocked) => blocked.url)).toEqual([
      'https://example.test/a',
      'https://example.test/b',
    ]);
  });

  it('is refused through window as well as through globalThis', async () => {
    await expect(window.fetch('/relative')).rejects.toThrow('/relative');

    expect(takeBlockedRequests()).toHaveLength(1);
  });

  it('is replaced by vi.stubGlobal for the length of one test', async () => {
    const mock = vi.fn().mockResolvedValue(new Response('ok'));
    vi.stubGlobal('fetch', mock);

    const response = await fetch('https://example.test/mocked');

    expect(await response.text()).toBe('ok');
    expect(mock).toHaveBeenCalledOnce();
    expect(takeBlockedRequests()).toEqual([]);
  });

  it('comes back after vi.unstubAllGlobals()', async () => {
    vi.stubGlobal('fetch', vi.fn());
    vi.unstubAllGlobals();

    await expect(fetch('https://example.test/after-unstub')).rejects.toThrow('after-unstub');

    expect(takeBlockedRequests()).toHaveLength(1);
  });

  it('comes back after a test that assigned globalThis.fetch directly', async () => {
    // GIVEN a test that replaces fetch by plain assignment and never puts it back
    globalThis.fetch = vi.fn().mockResolvedValue(new Response('assigned'));
    expect(await (await fetch('https://example.test/assigned')).text()).toBe('assigned');

    // WHEN the setup's afterEach reinstalls the guard
    installNetworkGuard();

    // THEN the next call is refused again
    await expect(fetch('https://example.test/next-call')).rejects.toThrow('next-call');
    expect(takeBlockedRequests()).toHaveLength(1);
  });
});

describe('a call without a URL', () => {
  it('is reported as "(no URL)"', async () => {
    await expect((fetch as () => Promise<Response>)()).rejects.toThrow('(no URL)');

    expect(takeBlockedRequests()).toEqual([{ api: 'fetch', url: '' }]);
  });
});

describe('swallowed requests', () => {
  it('are recorded and fail the test even when the code catches the refusal', async () => {
    await fetch('https://example.test/swallowed').catch(() => undefined);

    expect(() => failOnBlockedRequests()).toThrow(
      /tried to send 1 network request.*\n {2}fetch https:\/\/example\.test\/swallowed/
    );
  });

  it('are cleared by failOnBlockedRequests, so the next call passes', async () => {
    await fetch('https://example.test/once').catch(() => undefined);
    expect(() => failOnBlockedRequests()).toThrow('once');

    expect(() => failOnBlockedRequests()).not.toThrow();
    expect(takeBlockedRequests()).toEqual([]);
  });

  it('are listed together in one message', async () => {
    await fetch('https://example.test/one').catch(() => undefined);
    await fetch('https://example.test/two').catch(() => undefined);

    expect(() => failOnBlockedRequests()).toThrow(/2 network request[\s\S]*one[\s\S]*two/);
  });

  // The hook in tests/setup.ts turns the record into a failure of the test that made the
  // request. This test makes a request and swallows it, so only that hook can fail it, and
  // it passes only while the hook does.
  it.fails('fail the test that made them through the afterEach in tests/setup.ts', async () => {
    await fetch('https://example.test/swallowed-in-hook').catch(() => undefined);
  });
});

describe('XMLHttpRequest', () => {
  it('lets a request be opened and refuses to send it, naming the URL', () => {
    const request = new XMLHttpRequest();
    request.open('POST', 'https://example.test/xhr');
    request.setRequestHeader('X-Test', '1');

    expect(() => request.send('{}')).toThrow(
      /Unmocked network request: XMLHttpRequest https:\/\/example\.test\/xhr/
    );
    expect(takeBlockedRequests()).toEqual([
      { api: 'XMLHttpRequest', url: 'https://example.test/xhr' },
    ]);
  });

  it('keeps the state constants of the class it replaces', () => {
    expect(XMLHttpRequest.DONE).toBe(4);
    expect(new XMLHttpRequest().readyState).toBe(XMLHttpRequest.UNSENT);
  });

  it('is replaced by vi.stubGlobal for the length of one test', () => {
    const send = vi.fn();
    vi.stubGlobal(
      'XMLHttpRequest',
      class {
        open = vi.fn();
        send = send;
      }
    );

    new XMLHttpRequest().send();

    expect(send).toHaveBeenCalledOnce();
    expect(takeBlockedRequests()).toEqual([]);
  });

  it('is refused again after vi.unstubAllGlobals()', () => {
    vi.stubGlobal('XMLHttpRequest', vi.fn());
    vi.unstubAllGlobals();

    const request = new XMLHttpRequest();
    request.open('GET', '/after-unstub');

    expect(() => request.send()).toThrow('/after-unstub');
    expect(takeBlockedRequests()).toHaveLength(1);
  });
});

describe('WebSocket', () => {
  it('refuses to connect and names the URL', () => {
    expect(() => new WebSocket('wss://example.test/socket')).toThrow(
      /Unmocked network request: WebSocket wss:\/\/example\.test\/socket/
    );
    expect(takeBlockedRequests()).toEqual([
      { api: 'WebSocket', url: 'wss://example.test/socket' },
    ]);
  });

  it('keeps the state constants, which code compares readyState against', () => {
    expect([WebSocket.CONNECTING, WebSocket.OPEN, WebSocket.CLOSING, WebSocket.CLOSED]).toEqual([
      0, 1, 2, 3,
    ]);
  });

  it('is replaced by vi.stubGlobal and refused again after vi.unstubAllGlobals()', () => {
    const mock = vi.fn();
    vi.stubGlobal('WebSocket', mock);
    new WebSocket('wss://example.test/mocked');
    expect(mock).toHaveBeenCalledOnce();

    vi.unstubAllGlobals();

    expect(() => new WebSocket('wss://example.test/again')).toThrow('again');
    expect(takeBlockedRequests()).toHaveLength(1);
  });
});

describe('navigator.sendBeacon', () => {
  it('is refused with the URL in the message', () => {
    expect(() => navigator.sendBeacon('https://example.test/beacon', 'x')).toThrow(
      /navigator\.sendBeacon https:\/\/example\.test\/beacon/
    );
    expect(takeBlockedRequests()).toHaveLength(1);
  });

  it('is guarded again after a test removed it', () => {
    Object.defineProperty(navigator, 'sendBeacon', { value: undefined, configurable: true });

    installNetworkGuard();

    expect(() => navigator.sendBeacon('https://example.test/back', 'x')).toThrow('/back');
    expect(takeBlockedRequests()).toHaveLength(1);
  });
});
