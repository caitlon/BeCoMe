import { describe, it, expect, vi, afterEach } from 'vitest';
import { streamAssistantMessage } from '@/components/assistant/assistant-api';
import type { AssistantChatRequest } from '@/types/api';

// Unlike assistant-api.test.ts, this file leaves the real ApiClient in place and stubs only
// fetch, because the wrapping of an aborted fetch into a NetworkError happens inside it.

const request: AssistantChatRequest = { message: 'hi', history: [], project_id: null, locale: 'en' };

function stubFetchRejectingOnAbort(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('The operation was aborted', 'AbortError'))
          );
        })
    )
  );
}

describe('streamAssistantMessage through the real ApiClient', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('rejects with an AbortError when the signal aborts before the response headers arrive', async () => {
    stubFetchRejectingOnAbort();
    const controller = new AbortController();

    const promise = streamAssistantMessage(request, controller.signal);
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('rejects with an AbortError when the abort surfaces as a plain fetch failure', async () => {
    const controller = new AbortController();
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        controller.abort();
        return Promise.reject(new TypeError('Failed to fetch'));
      })
    );

    await expect(streamAssistantMessage(request, controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    });
  });

  it('still reports a network failure as a NetworkError when nothing aborted', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))));

    await expect(
      streamAssistantMessage(request, new AbortController().signal)
    ).rejects.toMatchObject({ kind: 'network' });
  });
});
