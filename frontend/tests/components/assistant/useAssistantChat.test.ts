import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { Storage } from 'happy-dom';
import i18n from '@/i18n';
import {
  STORAGE_PREFIX,
  clearAssistantHistory,
  useAssistantChat,
  type AssistantMessage,
} from '@/components/assistant/useAssistantChat';
import type { AssistantSseEvent } from '@/components/assistant/sse';
import {
  HttpError,
  NetworkError,
  RateLimitError,
  ServerError,
  StreamIncompleteError,
} from '@/lib/errors';
import type { AssistantChatResponse } from '@/types/api';

const mockStreamAssistantMessage = vi.fn();
vi.mock('@/components/assistant/assistant-api', () => ({
  streamAssistantMessage: (...args: unknown[]) => mockStreamAssistantMessage(...args),
}));

const mockReadAssistantSseStream = vi.fn();
vi.mock('@/components/assistant/sse', () => ({
  readAssistantSseStream: (...args: unknown[]) => mockReadAssistantSseStream(...args),
}));

const CHECKS = { citations_valid: true, numbers_grounded: true, ungrounded_numbers: [] };
const SOURCE = {
  n: 1, title: 'Method', section: 'Steps', snippet: 'The midpoint.', url: null, layer: 'public' as const,
};
const RESPONSE: AssistantChatResponse = {
  answer: 'The best compromise is the midpoint [1].',
  sources: [SOURCE],
  tools_used: ['search_docs'],
  checks: CHECKS,
  usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2, llm_calls: 1, complete: true },
  timing: { ttft_ms: 12, total_ms: 340 },
};

type Item = { event: AssistantSseEvent } | { error: unknown };

/**
 * Stands in for readAssistantSseStream: events are handed over one at a time and
 * an abort of the signal it was given throws an AbortError, as the real reader does.
 */
function openStream() {
  const items: Item[] = [];
  let wake: (() => void) | undefined;
  const push = (item: Item) => {
    items.push(item);
    wake?.();
  };
  mockReadAssistantSseStream.mockImplementation((_body: unknown, signal?: AbortSignal) =>
    (async function* () {
      signal?.addEventListener('abort', () =>
        push({ error: new DOMException('The operation was aborted', 'AbortError') })
      );
      for (;;) {
        while (items.length === 0) {
          await new Promise<void>((resolve) => {
            wake = resolve;
          });
        }
        const item = items.shift()!;
        if ('error' in item) throw item.error;
        yield item.event;
        if (item.event.type !== 'token') return;
      }
    })()
  );
  return {
    token: (text: string) => push({ event: { type: 'token', text } }),
    done: (response: AssistantChatResponse = RESPONSE) => push({ event: { type: 'done', response } }),
    error: (code: number, detail: string) => push({ event: { type: 'error', code, detail } }),
    fail: (error: unknown) => push({ error }),
  };
}

function storedMessage(
  index: number,
  role: 'user' | 'assistant',
  status: AssistantMessage['status'] = 'done',
  content = `${role} ${index}`
): AssistantMessage {
  return { id: `m${index}`, role, content, status, createdAt: 1000 + index };
}

function seed(messages: AssistantMessage[], userId = 'u1', projectId = 'general') {
  window.sessionStorage.setItem(`${STORAGE_PREFIX}:${userId}:${projectId}`, JSON.stringify(messages));
}

function stored(userId = 'u1', projectId = 'general'): AssistantMessage[] | null {
  const raw = window.sessionStorage.getItem(`${STORAGE_PREFIX}:${userId}:${projectId}`);
  return raw === null ? null : (JSON.parse(raw) as AssistantMessage[]);
}

function setup(props: { projectId?: string | null; userId?: string } = {}) {
  return renderHook(
    (p: { projectId: string | null; userId: string }) => useAssistantChat(p),
    { initialProps: { projectId: props.projectId ?? null, userId: props.userId ?? 'u1' } }
  );
}

type Chat = ReturnType<typeof setup>['result'];

/** Lets whatever a finished or aborted request still has queued run. */
const nextTick = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

/** Types the question and sends it, without waiting for the answer to finish. */
function ask(result: Chat, text = 'What is the best compromise?') {
  act(() => result.current.setDraft(text));
  act(() => {
    void result.current.sendMessage();
  });
}

describe('useAssistantChat', () => {
  beforeEach(() => {
    mockStreamAssistantMessage.mockReset();
    mockReadAssistantSseStream.mockReset();
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    mockStreamAssistantMessage.mockResolvedValue({ body: {} } as Response);
    window.sessionStorage.clear();
  });

  afterEach(async () => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    await i18n.changeLanguage('en');
  });

  describe('streaming', () => {
    it('appends each token to the pending answer as it arrives', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result);
      expect(result.current.isPending).toBe(true);
      stream.token('The best ');
      await waitFor(() => expect(result.current.messages[1].content).toBe('The best '));
      stream.token('compromise');

      await waitFor(() => expect(result.current.messages[1].content).toBe('The best compromise'));
      expect(result.current.messages[1].status).toBe('pending');
      expect(result.current.messages[0]).toMatchObject({
        role: 'user', content: 'What is the best compromise?', status: 'done',
      });
      expect(result.current.draft).toBe('');
    });

    it('takes the answer from a done event that no token preceded', async () => {
      openStream().done();
      const { result } = setup();

      ask(result);

      await waitFor(() => expect(result.current.messages[1].status).toBe('done'));
      expect(result.current.messages[1]).toMatchObject({ content: RESPONSE.answer, sources: [SOURCE] });
      expect(result.current.draft).toBe('');
    });

    it('logs the class of a failed turn and never its message', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result);
      stream.fail(new TypeError('secret host name'));

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(console.error).toHaveBeenCalledWith('[ERROR] Assistant turn failed', { error: 'TypeError' });
      expect(JSON.stringify(vi.mocked(console.error).mock.calls)).not.toContain('secret host name');
    });

    it('does not log a cancel', async () => {
      mockStreamAssistantMessage.mockImplementation(
        (_request: unknown, signal: AbortSignal) =>
          new Promise((_resolve, reject) => {
            signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
          })
      );
      const { result } = setup();
      ask(result);

      act(() => result.current.cancel());

      await waitFor(() => expect(result.current.messages[1].status).toBe('cancelled'));
      expect(console.error).not.toHaveBeenCalled();
    });

    it('replaces the text with the final answer and attaches the extras on done', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result);
      stream.token('The best');
      stream.done();

      await waitFor(() => expect(result.current.isPending).toBe(false));
      expect(result.current.messages[1]).toMatchObject({
        role: 'assistant',
        status: 'done',
        content: RESPONSE.answer,
        sources: [SOURCE],
        toolsUsed: ['search_docs'],
        checks: CHECKS,
        timing: { ttft_ms: 12, total_ms: 340 },
      });
      expect(result.current.messages[1].error).toBeUndefined();
    });

    it('keeps the partial text when the stream reports an error', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result);
      stream.token('Partial');
      stream.error(503, 'The model server is unavailable');

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1]).toMatchObject({
        content: 'Partial',
        error: { code: 503, detail: 'The model server is unavailable' },
      });
      expect(result.current.draft).toBe('');
    });

    it('restores the question into the box when the stream errors before any token', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result, 'Why?');
      stream.error(500, 'Boom');

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error).toEqual({ code: 500, detail: 'Boom' });
      expect(result.current.draft).toBe('Why?');
      expect(result.current.messages[0]).toMatchObject({ role: 'user', content: 'Why?' });
    });

    it.each([
      ['an incomplete stream', new StreamIncompleteError()],
      ['a network failure', new NetworkError('offline')],
      ['a TypeError the reader did not wrap', new TypeError('network error')],
      ['any other thrown value', new Error('something else')],
    ])('marks the answer cut after the first token on %s', async (_name, failure) => {
      const stream = openStream();
      const { result } = setup();

      ask(result);
      stream.token('Half an answer');
      stream.fail(failure);

      await waitFor(() => expect(result.current.messages[1].status).toBe('cut'));
      expect(result.current.messages[1].content).toBe('Half an answer');
      expect(result.current.messages[1].error).toBeUndefined();
      expect(result.current.draft).toBe('');
    });

    it('reports a TypeError before the first token as code 0 and restores the question', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result, 'Why?');
      stream.fail(new TypeError('network error'));

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error).toEqual({ code: 0, detail: 'network error' });
      expect(result.current.draft).toBe('Why?');
    });

    it('treats a token with empty text as no content', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result, 'Why?');
      stream.token('');
      stream.fail(new StreamIncompleteError());

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].content).toBe('');
      expect(result.current.draft).toBe('Why?');
    });

    it('reports code 0 and restores the question when the stream breaks before any token', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result, 'Why?');
      stream.fail(new StreamIncompleteError());

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error).toMatchObject({ code: 0 });
      expect(result.current.draft).toBe('Why?');
    });

    it('does not overwrite a new question the user typed while the failed one was running', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result, 'First');
      act(() => result.current.setDraft('Second'));
      stream.fail(new StreamIncompleteError());

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.draft).toBe('Second');
    });

    it('fails the turn when the response has no body', async () => {
      mockStreamAssistantMessage.mockResolvedValue({ body: null } as Response);
      openStream().done();
      const { result } = setup();

      ask(result);

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error).toMatchObject({ code: 0 });
    });

    it('fails the turn when the reader ends without done or error', async () => {
      mockReadAssistantSseStream.mockImplementation(() => (async function* () { /* no events */ })());
      const { result } = setup();

      ask(result);

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error?.code).toBe(0);
    });

    it('hands the reader the response body and the cancel signal', async () => {
      const body = {} as ReadableStream<Uint8Array>;
      mockStreamAssistantMessage.mockResolvedValue({ body } as Response);
      const stream = openStream();
      const { result } = setup();

      ask(result);
      stream.done();

      await waitFor(() => expect(result.current.isPending).toBe(false));
      const [readBody, signal] = mockReadAssistantSseStream.mock.calls[0];
      expect(readBody).toBe(body);
      expect(signal).toBe(mockStreamAssistantMessage.mock.calls[0][1]);
    });
  });

  describe('cancel and clear', () => {
    it('marks the answer cancelled, keeps the partial and applies nothing afterwards', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      act(() => result.current.cancel());
      stream.token(' late');
      stream.done();

      await waitFor(() => expect(result.current.messages[1].status).toBe('cancelled'));
      expect(mockStreamAssistantMessage.mock.calls[0][1].aborted).toBe(true);
      expect(result.current.isPending).toBe(false);
      expect(result.current.messages[1].content).toBe('Partial');
      expect(result.current.draft).toBe('');
    });

    it('applies no event that arrives after the cancel, even from a reader that ignores the signal', async () => {
      let release: () => void = () => undefined;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      mockReadAssistantSseStream.mockImplementation(() =>
        (async function* () {
          yield { type: 'token', text: 'Partial' } as const;
          await gate;
          yield { type: 'token', text: ' late' } as const;
          yield { type: 'done', response: RESPONSE } as const;
        })()
      );
      const { result } = setup();
      ask(result);
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      act(() => result.current.cancel());
      release();

      await waitFor(() => expect(result.current.messages[1].status).toBe('cancelled'));
      expect(result.current.messages[1].content).toBe('Partial');
      expect(result.current.messages[1].sources).toBeUndefined();
    });

    it('cancels a request that has not opened its stream yet', async () => {
      mockStreamAssistantMessage.mockImplementation(
        (_request: unknown, signal: AbortSignal) =>
          new Promise((_resolve, reject) => {
            signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
          })
      );
      const { result } = setup();
      ask(result);

      act(() => result.current.cancel());

      await waitFor(() => expect(result.current.messages[1].status).toBe('cancelled'));
      expect(result.current.messages[1].content).toBe('');
      expect(result.current.draft).toBe('');
    });

    it('empties the conversation, aborts the request in flight and drops the stored copy', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(stored()).toHaveLength(2));

      act(() => result.current.clear());

      expect(result.current.messages).toHaveLength(0);
      expect(mockStreamAssistantMessage.mock.calls[0][1].aborted).toBe(true);
      expect(stored()).toBeNull();
      await waitFor(() => expect(result.current.isPending).toBe(false));
      expect(result.current.messages).toHaveLength(0);
    });

    it('keeps the second request cancellable while the cleared first one is still unwinding', async () => {
      // A reader that throws an AbortError as soon as it looks at an aborted signal,
      // but only once its gate is opened, so the first request unwinds late.
      const gates: (() => void)[] = [];
      mockReadAssistantSseStream.mockImplementation((_body: unknown, signal?: AbortSignal) =>
        (async function* () {
          await new Promise<void>((resolve) => gates.push(resolve));
          if (signal?.aborted) throw new DOMException('The operation was aborted', 'AbortError');
          yield { type: 'token', text: 'x' } as const;
        })()
      );
      const { result } = setup();
      ask(result, 'first');
      act(() => result.current.clear());
      ask(result, 'second');
      await nextTick();
      expect(gates).toHaveLength(2);

      gates[0]();
      await nextTick();
      act(() => result.current.setDraft('third'));
      act(() => {
        void result.current.sendMessage();
      });
      expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(2);
      act(() => result.current.cancel());

      expect(mockStreamAssistantMessage.mock.calls[1][1].aborted).toBe(true);
    });

    it('drops the stored copy on clear even while a token render is still on its way', async () => {
      // A token that has been read but not yet rendered must not cost the clear its
      // write. Whether it lands before the clear's own render depends on scheduling,
      // so the order is tried many times over.
      for (let round = 0; round < 60; round += 1) {
        const stream = openStream();
        const { result, unmount } = setup();
        ask(result);
        stream.token('Partial');
        await waitFor(() => expect(stored()).toHaveLength(2));

        act(() => result.current.clear());

        expect(stored()).toBeNull();
        unmount();
        await nextTick();
        window.sessionStorage.clear();
      }
    });

    it('lets a new question go out right after a clear', async () => {
      openStream();
      const { result } = setup();
      ask(result, 'first');
      act(() => result.current.clear());

      ask(result, 'second');

      await waitFor(() => expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(2));
      expect(mockStreamAssistantMessage.mock.calls[1][0].message).toBe('second');
    });

    it('sends once when a clear is followed by two sends in a row', async () => {
      openStream();
      const { result } = setup();
      ask(result, 'first');
      act(() => result.current.clear());
      act(() => result.current.setDraft('second'));

      act(() => {
        void result.current.sendMessage();
        void result.current.sendMessage();
      });

      expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(2);
      expect(mockStreamAssistantMessage.mock.calls[1][0].message).toBe('second');
      expect(result.current.messages).toHaveLength(2);
    });

    it('aborts the request when the hook unmounts and does not store the partial', async () => {
      const stream = openStream();
      const { result, unmount } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      unmount();
      await nextTick();

      expect(mockStreamAssistantMessage.mock.calls[0][1].aborted).toBe(true);
      // Only what the append wrote is there: the answer still empty.
      expect(stored()?.[1]).toMatchObject({ status: 'pending', content: '' });
    });

    it('leaves storage alone when it unmounts with nothing in flight', () => {
      const { unmount } = setup();

      unmount();

      expect(stored()).toBeNull();
    });
  });

  describe('request errors', () => {
    it('carries the status and Retry-After of a 429 and restores the question', async () => {
      mockStreamAssistantMessage.mockRejectedValueOnce(new RateLimitError('Too many requests', 30));
      const { result } = setup();

      ask(result, 'hi');

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error).toEqual({
        code: 429, detail: 'Too many requests', retryAfter: 30,
      });
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0]).toMatchObject({ role: 'user', content: 'hi' });
      expect(result.current.draft).toBe('hi');
    });

    it('reports a 429 without a Retry-After header with no retryAfter', async () => {
      mockStreamAssistantMessage.mockRejectedValueOnce(new RateLimitError('Too many requests'));
      const { result } = setup();

      ask(result, 'hi');

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error?.code).toBe(429);
      expect(result.current.messages[1].error?.retryAfter).toBeUndefined();
      expect(result.current.draft).toBe('hi');
    });

    it.each([
      ['a 503', new ServerError('Service Unavailable', 503), 503],
      ['a 404', new HttpError('Not Found', 404), 404],
      ['a 422', new HttpError('Unprocessable Entity', 422), 422],
    ])('classifies %s by its status code', async (_name, failure, code) => {
      mockStreamAssistantMessage.mockRejectedValueOnce(failure);
      const { result } = setup();

      ask(result, 'hi');

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error).toEqual({ code, detail: failure.message });
      expect(result.current.draft).toBe('hi');
    });

    it('reports an unclassified failure as code 0', async () => {
      mockStreamAssistantMessage.mockRejectedValueOnce('plain string');
      const { result } = setup();

      ask(result, 'hi');

      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));
      expect(result.current.messages[1].error).toEqual({ code: 0, detail: 'plain string' });
    });
  });

  describe('sending', () => {
    it('sends the project, the locale and a history that leaves out the new question', async () => {
      await i18n.changeLanguage('cs');
      openStream().done();
      const { result } = setup({ projectId: 'project-1' });

      ask(result, 'hi');

      await waitFor(() => expect(result.current.isPending).toBe(false));
      expect(mockStreamAssistantMessage.mock.calls[0][0]).toEqual({
        message: 'hi', history: [], project_id: 'project-1', locale: 'cs',
      });
    });

    it('does nothing for a blank draft', async () => {
      const { result } = setup();

      act(() => result.current.setDraft('   '));
      await act(() => result.current.sendMessage());

      expect(mockStreamAssistantMessage).not.toHaveBeenCalled();
      expect(result.current.messages).toHaveLength(0);
    });

    it('ignores a send while one is already pending', async () => {
      openStream();
      const { result } = setup();
      ask(result, 'first');
      await waitFor(() => expect(result.current.isPending).toBe(true));

      act(() => result.current.setDraft('second'));
      await act(() => result.current.sendMessage());

      expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(1);
    });

    it('sends once when sendMessage is called twice in the same tick', () => {
      openStream();
      const { result } = setup();
      act(() => result.current.setDraft('hi'));

      act(() => {
        void result.current.sendMessage();
        void result.current.sendMessage();
      });

      expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(1);
      expect(result.current.messages).toHaveLength(2);
    });

    it('counts the seconds a pending answer has waited and exposes when it started', () => {
      vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] });
      vi.setSystemTime(50_000);
      openStream();
      const { result } = setup();

      ask(result);
      expect(result.current.startedAt).toBe(50_000);
      expect(result.current.pendingSeconds).toBe(0);
      act(() => {
        vi.advanceTimersByTime(3000);
      });

      expect(result.current.pendingSeconds).toBe(3);
      expect(result.current.messages[1].createdAt).toBe(50_000);
    });

    it('reports no start time and no wait while nothing is pending', () => {
      const { result } = setup();

      expect(result.current.startedAt).toBeNull();
      expect(result.current.pendingSeconds).toBe(0);
    });
  });

  describe('retry', () => {
    it('sends the given question as a new turn, whatever is in the box', async () => {
      const stream = openStream();
      const { result } = setup({ projectId: 'project-1' });
      ask(result, 'Why?');
      stream.token('Half');
      stream.fail(new StreamIncompleteError());
      await waitFor(() => expect(result.current.messages[1].status).toBe('cut'));
      act(() => result.current.setDraft('something else'));

      openStream().done();
      await act(() => result.current.retry('Why?'));

      expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(2);
      expect(mockStreamAssistantMessage.mock.calls[1][0]).toMatchObject({
        message: 'Why?', project_id: 'project-1',
      });
      expect(result.current.messages).toHaveLength(4);
      expect(result.current.messages[3]).toMatchObject({ status: 'done', content: RESPONSE.answer });
      expect(result.current.draft).toBe('something else');
    });

    it('empties the box when the failed question was put back into it', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'Why?');
      stream.error(503, 'down');
      await waitFor(() => expect(result.current.draft).toBe('Why?'));

      openStream().done();
      await act(() => result.current.retry('Why?'));

      expect(result.current.draft).toBe('');
      expect(result.current.messages[3].status).toBe('done');
    });

    it('does not send the failed question a second time in the history', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'Why?');
      stream.error(503, 'down');
      await waitFor(() => expect(result.current.isPending).toBe(false));

      openStream().done();
      await act(() => result.current.retry('Why?'));

      expect(mockStreamAssistantMessage.mock.calls[1][0].history).toEqual([]);
    });

    it('leaves the question of a cut turn out of the history of its retry', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'Why?');
      stream.token('Half');
      stream.fail(new StreamIncompleteError());
      await waitFor(() => expect(result.current.messages[1].status).toBe('cut'));

      openStream().done();
      await act(() => result.current.retry('Why?'));

      expect(mockStreamAssistantMessage.mock.calls[1][0].history).toEqual([]);
      expect(result.current.messages[0].status).toBe('error');
      expect(result.current.messages).toHaveLength(4);
      expect(result.current.messages[2]).toMatchObject({ role: 'user', content: 'Why?', status: 'done' });
    });

    it('keeps the answered turns before the retried one in the history', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'q0');
      stream.done({ ...RESPONSE, answer: 'a0' });
      await waitFor(() => expect(result.current.isPending).toBe(false));
      ask(result, 'q1');
      stream.token('Half');
      stream.fail(new StreamIncompleteError());
      await waitFor(() => expect(result.current.messages[3].status).toBe('cut'));

      openStream().done();
      await act(() => result.current.retry('q1'));

      expect(mockStreamAssistantMessage.mock.calls[2][0].history).toEqual([
        { role: 'user', content: 'q0' },
        { role: 'assistant', content: 'a0' },
      ]);
    });

    it('leaves an answered question alone when its text is asked again', async () => {
      openStream().done({ ...RESPONSE, answer: 'a0' });
      const { result } = setup();
      ask(result, 'Why?');
      await waitFor(() => expect(result.current.isPending).toBe(false));

      openStream().done();
      await act(() => result.current.retry('Why?'));

      expect(result.current.messages[0].status).toBe('done');
      expect(mockStreamAssistantMessage.mock.calls[1][0].history).toEqual([
        { role: 'user', content: 'Why?' },
        { role: 'assistant', content: 'a0' },
      ]);
    });

    it('marks no earlier question failed when the text is not that of the failed turn', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'Why?');
      stream.token('Half');
      stream.fail(new StreamIncompleteError());
      await waitFor(() => expect(result.current.messages[1].status).toBe('cut'));

      openStream().done();
      await act(() => result.current.retry('Something else'));

      expect(result.current.messages[0].status).toBe('done');
    });

    it('is refused while a turn is pending, and for an empty question', async () => {
      openStream();
      const { result } = setup();
      ask(result, 'first');
      await waitFor(() => expect(result.current.isPending).toBe(true));

      await act(() => result.current.retry('again'));
      await act(() => result.current.retry(''));

      expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(1);
    });
  });

  describe('history window', () => {
    /** One answered exchange, `n` times over, each answer `a<i>` to the question `q<i>`. */
    async function converse(result: Chat, stream: ReturnType<typeof openStream>, n: number) {
      for (let i = 0; i < n; i += 1) {
        ask(result, `q${i}`);
        stream.done({ ...RESPONSE, answer: `a${i}` });
        await waitFor(() => expect(result.current.isPending).toBe(false));
      }
    }

    it('sends the last 20 answered entries, oldest first', async () => {
      const stream = openStream();
      const { result } = setup();
      await converse(result, stream, 12);

      ask(result, 'next');

      const { history } = mockStreamAssistantMessage.mock.calls[12][0];
      expect(history).toHaveLength(20);
      expect(history[0]).toEqual({ role: 'user', content: 'q2' });
      expect(history[19]).toEqual({ role: 'assistant', content: 'a11' });
    });

    it('leaves out partial, failed, cut and cancelled answers', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'q0');
      stream.done({ ...RESPONSE, answer: 'a0' });
      await waitFor(() => expect(result.current.isPending).toBe(false));
      ask(result, 'q1');
      stream.error(500, 'ERROR');
      await waitFor(() => expect(result.current.isPending).toBe(false));
      ask(result, 'q2');
      stream.token('CUT');
      stream.fail(new StreamIncompleteError());
      await waitFor(() => expect(result.current.isPending).toBe(false));
      ask(result, 'q3');
      stream.token('CANCELLED');
      await waitFor(() => expect(result.current.messages[7].content).toBe('CANCELLED'));
      act(() => result.current.cancel());
      await waitFor(() => expect(result.current.isPending).toBe(false));
      ask(result, 'q4');
      stream.token('PENDING');
      await waitFor(() => expect(result.current.messages[9].content).toBe('PENDING'));

      // A send while q4 is pending is refused, so no request can carry the partial.
      act(() => result.current.setDraft('blocked'));
      await act(() => result.current.sendMessage());
      expect(mockStreamAssistantMessage).toHaveBeenCalledTimes(5);

      stream.done({ ...RESPONSE, answer: 'a4' });
      await waitFor(() => expect(result.current.isPending).toBe(false));
      ask(result, 'next');

      // q1 failed before any answer, so its question is not sent either.
      expect(mockStreamAssistantMessage.mock.calls[5][0].history).toEqual([
        { role: 'user', content: 'q0' },
        { role: 'assistant', content: 'a0' },
        { role: 'user', content: 'q2' },
        { role: 'user', content: 'q3' },
        { role: 'user', content: 'q4' },
        { role: 'assistant', content: 'a4' },
      ]);
    });

    it('exposes the index of the oldest message inside the window', async () => {
      const stream = openStream();
      const { result } = setup();

      await converse(result, stream, 12);

      // 24 answered messages: the last 20 start at index 4.
      expect(result.current.historyWindowStart).toBe(4);
    });

    it('starts the window at the first message while fewer than 20 are answered', async () => {
      const stream = openStream();
      const { result } = setup();

      await converse(result, stream, 1);

      expect(result.current.historyWindowStart).toBe(0);
    });

    it('does not send the question of a failed turn again with the next request', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'failed question');
      stream.error(500, 'Boom');
      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));

      expect(result.current.messages[0]).toMatchObject({ role: 'user', status: 'error' });
      expect(result.current.historyWindowStart).toBe(-1);
      expect(result.current.draft).toBe('failed question');
      act(() => {
        void result.current.sendMessage();
      });

      expect(mockStreamAssistantMessage.mock.calls[1][0]).toMatchObject({
        message: 'failed question',
        history: [],
      });
    });

    it('keeps the question of a turn that failed after some text was shown', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result, 'half answered');
      stream.token('Partial');
      stream.error(500, 'Boom');
      await waitFor(() => expect(result.current.messages[1].status).toBe('error'));

      expect(result.current.messages[0].status).toBe('done');
    });

    it('counts a question that is sent but not yet answered as the start of the window', () => {
      openStream();
      const { result } = setup();

      ask(result, 'unanswered');

      expect(result.current.historyWindowStart).toBe(0);
    });

    it('reports -1 when nothing has been answered', () => {
      const { result } = setup();

      expect(result.current.historyWindowStart).toBe(-1);
    });
  });

  describe('the conversation list', () => {
    it('keeps at most the last 40 messages', async () => {
      const stream = openStream();
      const { result } = setup();

      for (let i = 0; i < 21; i += 1) {
        ask(result, `q${i}`);
        stream.done();
        await waitFor(() => expect(result.current.isPending).toBe(false));
      }

      expect(result.current.messages).toHaveLength(40);
      expect(result.current.messages[0]).toMatchObject({ role: 'user', content: 'q1' });
      expect(result.current.messages[39]).toMatchObject({ role: 'assistant', status: 'done' });
    });

    it('starts an empty conversation for another project', async () => {
      const stream = openStream();
      const { result, rerender } = setup();
      ask(result);
      stream.done();
      await waitFor(() => expect(result.current.isPending).toBe(false));
      expect(result.current.messages).toHaveLength(2);

      rerender({ projectId: 'p2', userId: 'u1' });

      expect(result.current.messages).toEqual([]);
    });

    it('aborts a request when the conversation changes under it and keeps it out of the new one', async () => {
      const stream = openStream();
      const { result, rerender } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      rerender({ projectId: 'p2', userId: 'u1' });

      expect(mockStreamAssistantMessage.mock.calls[0][1].aborted).toBe(true);
      expect(result.current.messages).toEqual([]);
      await waitFor(() => expect(result.current.isPending).toBe(false));
      expect(result.current.messages).toEqual([]);
    });
  });

  describe('persistence', () => {
    it('saves the conversation under the user and project key', async () => {
      const stream = openStream();
      const { result } = setup({ projectId: 'p1', userId: 'u7' });

      ask(result, 'hi');
      await waitFor(() => expect(stored('u7', 'p1')?.[0].content).toBe('hi'));
      stream.token('Part');
      stream.done();

      await waitFor(() => expect(stored('u7', 'p1')?.[1].status).toBe('done'));
      expect(stored('u7', 'p1')?.map((m) => m.role)).toEqual(['user', 'assistant']);
      expect(stored('u7', 'general')).toBeNull();
      expect(stored('u1', 'p1')).toBeNull();
    });

    it('loads the saved conversation on mount', () => {
      seed([storedMessage(0, 'user'), storedMessage(1, 'assistant')], 'u1', 'p1');

      const { result } = setup({ projectId: 'p1' });

      expect(result.current.messages.map((m) => m.content)).toEqual(['user 0', 'assistant 1']);
    });

    it('turns a message stored as pending into a cut one on load', () => {
      seed([storedMessage(0, 'user'), storedMessage(1, 'assistant', 'pending', 'Half')]);

      const { result } = setup();

      expect(result.current.messages[1]).toMatchObject({ status: 'cut', content: 'Half' });
      expect(result.current.isPending).toBe(false);
    });

    it('keeps at most the last 40 messages, in memory after a load and in storage', async () => {
      seed(Array.from({ length: 45 }, (_, i) => storedMessage(i, i % 2 === 0 ? 'user' : 'assistant')));
      openStream().done();
      const { result } = setup();
      expect(result.current.messages).toHaveLength(40);
      expect(result.current.messages[0].id).toBe('m5');

      ask(result, 'next');

      await waitFor(() => expect(result.current.isPending).toBe(false));
      expect(stored()).toHaveLength(40);
      expect(stored()?.[39]).toMatchObject({ role: 'assistant', content: RESPONSE.answer });
    });

    it.each([
      ['not JSON', 'not json'],
      ['not a list', '{"a":1}'],
    ])('starts empty when the stored value is %s', (_name, raw) => {
      window.sessionStorage.setItem(`${STORAGE_PREFIX}:u1:general`, raw);

      const { result } = setup();

      expect(result.current.messages).toEqual([]);
    });

    it('drops stored entries that are not messages', () => {
      seed([
        storedMessage(0, 'user'),
        { id: 1 } as unknown as AssistantMessage,
        null as unknown as AssistantMessage,
        { ...storedMessage(2, 'assistant'), status: 'weird' as AssistantMessage['status'] },
        { ...storedMessage(3, 'assistant'), role: 'system' as AssistantMessage['role'] },
      ]);

      const { result } = setup();

      expect(result.current.messages.map((m) => m.id)).toEqual(['m0']);
    });

    it('keeps a stored message whose optional parts have the right shape', () => {
      const full = {
        ...storedMessage(1, 'assistant'),
        error: { code: 429, detail: 'Too many requests', retryAfter: 30 },
        sources: [SOURCE],
        toolsUsed: ['search_docs'],
        checks: CHECKS,
        timing: { ttft_ms: 12, total_ms: 340 },
      };
      seed([storedMessage(0, 'user'), full as AssistantMessage]);

      const { result } = setup();

      expect(result.current.messages[1]).toEqual(full);
    });

    it.each([
      ['an error that is not an object', { error: 'boom' }],
      ['an error without a numeric code', { error: { code: '500', detail: 'x' } }],
      ['an error without a string detail', { error: { code: 500, detail: 7 } }],
      ['an error with a retryAfter that is not a number', { error: { code: 429, detail: 'x', retryAfter: '30' } }],
      ['a null error', { error: null }],
      ['sources that are not a list', { sources: { n: 1 } }],
      ['toolsUsed that is not a list', { toolsUsed: 'search_docs' }],
      ['checks that are a list', { checks: [] }],
      ['checks that are a string', { checks: 'ok' }],
      ['timing that is not an object', { timing: 12 }],
    ])('drops a stored message with %s', (_name, bad) => {
      seed([storedMessage(0, 'user'), { ...storedMessage(1, 'assistant'), ...bad } as unknown as AssistantMessage]);

      const { result } = setup();

      expect(result.current.messages.map((m) => m.id)).toEqual(['m0']);
    });

    it('switches to the conversation of another project and back', async () => {
      seed([storedMessage(0, 'user')], 'u1', 'general');
      seed([storedMessage(1, 'user'), storedMessage(2, 'assistant')], 'u1', 'p2');
      const { result, rerender } = setup();
      expect(result.current.messages).toHaveLength(1);

      rerender({ projectId: 'p2', userId: 'u1' });
      expect(result.current.messages).toHaveLength(2);

      rerender({ projectId: null, userId: 'u1' });
      expect(result.current.messages.map((m) => m.id)).toEqual(['m0']);
      expect(stored('u1', 'p2')).toHaveLength(2);
    });

    it('does not show one user the conversation of another', () => {
      seed([storedMessage(0, 'user')], 'u1');

      const { result } = setup({ userId: 'u2' });

      expect(result.current.messages).toEqual([]);
    });

    it('does not store the partial of an answer cut off by a conversation change', async () => {
      const stream = openStream();
      const { result, rerender } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      rerender({ projectId: 'p2', userId: 'u1' });

      expect(mockStreamAssistantMessage.mock.calls[0][1].aborted).toBe(true);
      expect(result.current.messages).toEqual([]);
      await waitFor(() => expect(result.current.isPending).toBe(false));
      expect(result.current.messages).toEqual([]);
      expect(stored('u1', 'general')?.[1]).toMatchObject({ status: 'pending', content: '' });
      expect(stored('u1', 'p2')).toBeNull();
    });

    it('swaps to the conversation of another user and aborts the request in flight', async () => {
      seed([storedMessage(0, 'user'), storedMessage(1, 'assistant')], 'u2');
      const stream = openStream();
      const { result, rerender } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      rerender({ projectId: null, userId: 'u2' });
      await nextTick();

      expect(mockStreamAssistantMessage.mock.calls[0][1].aborted).toBe(true);
      expect(result.current.messages.map((m) => m.id)).toEqual(['m0', 'm1']);
      expect(result.current.isPending).toBe(false);
      expect(stored('u2')?.map((m) => m.id)).toEqual(['m0', 'm1']);
    });

    it('writes nothing on mount, whatever it loaded', () => {
      seed([storedMessage(0, 'user'), storedMessage(1, 'assistant', 'pending', 'Half')]);
      const setItem = vi.spyOn(window.sessionStorage, 'setItem');
      const removeItem = vi.spyOn(window.sessionStorage, 'removeItem');

      setup();
      setup({ userId: 'nobody' });

      expect(setItem).not.toHaveBeenCalled();
      expect(removeItem).not.toHaveBeenCalled();
    });

    it('turns a stored pending answer that has no text into an empty cut one', () => {
      seed([storedMessage(0, 'user'), storedMessage(1, 'assistant', 'pending', '')]);

      const { result } = setup();

      expect(result.current.messages.map((m) => m.id)).toEqual(['m0', 'm1']);
      expect(result.current.messages[1]).toMatchObject({ status: 'cut', content: '' });
      expect(result.current.isPending).toBe(false);
    });

    it('removes the stored copy when an idle conversation is cleared', () => {
      seed([storedMessage(0, 'user'), storedMessage(1, 'assistant')]);
      const { result } = setup();
      expect(result.current.messages).toHaveLength(2);

      act(() => result.current.clear());

      expect(result.current.messages).toEqual([]);
      expect(stored()).toBeNull();
    });

    it('leaves storage empty when sign-out clears it and the panel then unmounts with a turn in flight', async () => {
      const stream = openStream();
      const { result, unmount } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      clearAssistantHistory();
      unmount();
      await nextTick();

      expect(stored()).toBeNull();
    });

    it('leaves storage empty when sign-out clears it and the turn then settles in a mounted hook', async () => {
      const stream = openStream();
      const { result } = setup();
      ask(result);
      stream.token('Partial');
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      clearAssistantHistory();
      stream.done();

      await waitFor(() => expect(result.current.messages[1].status).toBe('done'));
      expect(stored()).toBeNull();
    });

    it('leaves storage empty when the turn settles after clear()', async () => {
      let release: () => void = () => undefined;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      mockReadAssistantSseStream.mockImplementation(() =>
        (async function* () {
          yield { type: 'token', text: 'Partial' } as const;
          await gate;
          yield { type: 'done', response: RESPONSE } as const;
        })()
      );
      const { result } = setup();
      ask(result);
      await waitFor(() => expect(result.current.messages[1].content).toBe('Partial'));

      act(() => result.current.clear());
      release();
      await nextTick();

      expect(result.current.messages).toEqual([]);
      expect(stored()).toBeNull();
    });

    it('keeps working when storage is full', async () => {
      const setItem = vi.spyOn(window.sessionStorage, 'setItem').mockImplementation(() => {
        throw new DOMException('The quota has been exceeded', 'QuotaExceededError');
      });
      const reported: unknown[] = [];
      const onError = (event: Event) => reported.push(event);
      window.addEventListener('error', onError);
      openStream().done();
      const { result } = setup();

      ask(result, 'hi');

      await waitFor(() => expect(result.current.messages[1]?.status).toBe('done'));
      window.removeEventListener('error', onError);
      expect(setItem).toHaveBeenCalled();
      expect(reported).toEqual([]);
    });

    it('keeps working when storage refuses every read and write', async () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new DOMException('blocked', 'SecurityError');
      });
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new DOMException('blocked', 'SecurityError');
      });
      vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
        throw new DOMException('blocked', 'SecurityError');
      });
      // React reports an error thrown from an effect on the window, not to the test.
      const reported: unknown[] = [];
      const onError = (event: Event) => reported.push(event);
      window.addEventListener('error', onError);
      openStream().done();
      const { result } = setup();

      ask(result, 'hi');

      await waitFor(() => expect(result.current.messages[1]?.status).toBe('done'));
      act(() => result.current.clear());
      window.removeEventListener('error', onError);
      expect(result.current.messages).toEqual([]);
      expect(reported).toEqual([]);
    });

    it('writes storage when a turn is appended and when it settles, never per token', async () => {
      const setItem = vi.spyOn(window.sessionStorage, 'setItem');
      const stream = openStream();
      const { result } = setup();

      ask(result, 'hi');
      await waitFor(() => expect(stored()).toHaveLength(2));
      expect(setItem).toHaveBeenCalledTimes(1);
      for (let i = 0; i < 25; i += 1) stream.token(`t${i} `);
      await waitFor(() => expect(result.current.messages[1].content).toContain('t24 '));
      expect(setItem).toHaveBeenCalledTimes(1);
      stream.done();

      await waitFor(() => expect(stored()?.[1].status).toBe('done'));
      expect(setItem).toHaveBeenCalledTimes(2);
    });

    it('stores a turn that fails before any token', async () => {
      mockStreamAssistantMessage.mockRejectedValueOnce(new HttpError('Not Found', 404));
      const { result } = setup();

      ask(result, 'hi');

      await waitFor(() => expect(stored()?.[1].status).toBe('error'));
      expect(stored()?.[1].error).toEqual({ code: 404, detail: 'Not Found' });
    });

    it('stores a cut answer with its partial text', async () => {
      const stream = openStream();
      const { result } = setup();

      ask(result);
      stream.token('Half');
      stream.fail(new StreamIncompleteError());

      await waitFor(() => expect(stored()?.[1].status).toBe('cut'));
      expect(stored()?.[1].content).toBe('Half');
    });
  });
});

describe('clearAssistantHistory', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('removes every conversation of every user and project and nothing else', () => {
    seed([storedMessage(0, 'user')], 'u1', 'general');
    seed([storedMessage(0, 'user')], 'u1', 'p1');
    seed([storedMessage(0, 'user')], 'u2', 'p1');
    window.sessionStorage.setItem('theme', 'dark');
    window.sessionStorage.setItem(`${STORAGE_PREFIX}x`, 'no colon, not ours');

    clearAssistantHistory();

    expect(window.sessionStorage.length).toBe(2);
    expect(window.sessionStorage.getItem('theme')).toBe('dark');
    expect(window.sessionStorage.getItem(`${STORAGE_PREFIX}x`)).not.toBeNull();
  });

  it('does not throw when storage is blocked', () => {
    vi.spyOn(window.sessionStorage, 'key').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    seed([storedMessage(0, 'user')]);

    expect(() => clearAssistantHistory()).not.toThrow();
  });
});
