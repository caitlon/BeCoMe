import { describe, it, expect } from 'vitest';
import { readAssistantSseStream } from '@/components/assistant/sse';
import type { AssistantSseEvent } from '@/components/assistant/sse';
import { NetworkError, StreamIncompleteError } from '@/lib/errors';

const encoder = new TextEncoder();

const DONE_PAYLOAD = {
  answer: 'Hi',
  sources: [],
  tools_used: [],
  checks: { citations_valid: true, numbers_grounded: true, ungrounded_numbers: [] },
  usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2, llm_calls: 1, complete: true },
  timing: { ttft_ms: 10, total_ms: 20 },
};

function frame(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}

function streamFromChunks(chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        const chunk = chunks[index];
        controller.enqueue(typeof chunk === 'string' ? encoder.encode(chunk) : chunk);
        index += 1;
      } else {
        controller.close();
      }
    },
  });
}

/** A body that never delivers anything: a read on it stays pending. */
function stalledBody(): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({ pull: () => new Promise<void>(() => {}) });
}

async function collect(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal
): Promise<AssistantSseEvent[]> {
  const events: AssistantSseEvent[] = [];
  for await (const event of readAssistantSseStream(stream, signal)) {
    events.push(event);
  }
  return events;
}

describe('readAssistantSseStream', () => {
  it('yields the tokens and then the done response', async () => {
    const events = await collect(
      streamFromChunks([
        frame('token', { text: 'Hel' }),
        frame('token', { text: 'lo' }),
        frame('done', DONE_PAYLOAD),
      ])
    );

    expect(events).toEqual([
      { type: 'token', text: 'Hel' },
      { type: 'token', text: 'lo' },
      { type: 'done', response: DONE_PAYLOAD },
    ]);
  });

  it('yields an error event in place of done', async () => {
    const events = await collect(
      streamFromChunks([
        frame('token', { text: 'Hi' }),
        frame('error', { code: 503, detail: 'The assistant is temporarily unavailable' }),
      ])
    );

    expect(events).toEqual([
      { type: 'token', text: 'Hi' },
      { type: 'error', code: 503, detail: 'The assistant is temporarily unavailable' },
    ]);
  });

  it('reassembles an event whose line is cut by a chunk boundary', async () => {
    const whole = frame('token', { text: 'Hi' }) + frame('done', DONE_PAYLOAD);
    const cut = whole.indexOf('"text"') + 3;

    const events = await collect(streamFromChunks([whole.slice(0, cut), whole.slice(cut)]));

    expect(events).toEqual([
      { type: 'token', text: 'Hi' },
      { type: 'done', response: DONE_PAYLOAD },
    ]);
  });

  it('reassembles a blank-line separator split across two chunks', async () => {
    const events = await collect(
      streamFromChunks([
        'event: token\ndata: {"text":"Hi"}\n',
        '\n' + frame('done', DONE_PAYLOAD),
      ])
    );

    expect(events.map((event) => event.type)).toEqual(['token', 'done']);
  });

  it('keeps a multibyte character that arrives split across chunks', async () => {
    const bytes = encoder.encode(frame('token', { text: 'Příliš žluťoučký' }) + frame('done', DONE_PAYLOAD));
    const twoByteLetterIndex = bytes.indexOf(0xc5); // index of the lead byte of a two-byte letter
    const events = await collect(streamFromChunks([bytes.slice(0, twoByteLetterIndex + 1), bytes.slice(twoByteLetterIndex + 1)]));

    expect(events[0]).toEqual({ type: 'token', text: 'Příliš žluťoučký' });
  });

  it('keeps a four-byte character split byte by byte', async () => {
    const bytes = encoder.encode(frame('token', { text: 'a\u{1F600}b' }) + frame('done', DONE_PAYLOAD));
    const chunks = Array.from(bytes, (byte) => Uint8Array.of(byte));

    const events = await collect(streamFromChunks(chunks));

    expect(events[0]).toEqual({ type: 'token', text: 'a\u{1F600}b' });
  });

  it('accepts a raw U+2028 inside the JSON data without treating it as a line break', async () => {
    const lineSeparator = String.fromCharCode(0x2028);
    const events = await collect(
      streamFromChunks([
        `event: token\ndata: {"text":"a${lineSeparator}b"}\n\n`,
        frame('done', DONE_PAYLOAD),
      ])
    );

    expect(events[0]).toEqual({ type: 'token', text: `a${lineSeparator}b` });
  });

  it('skips an event with an unknown name and a block with no event line', async () => {
    const events = await collect(
      streamFromChunks([
        ': keep-alive\n\n',
        'event: tool\ndata: {"name":"search_docs"}\n\n',
        frame('token', { text: 'Hi' }),
        frame('done', DONE_PAYLOAD),
      ])
    );

    expect(events.map((event) => event.type)).toEqual(['token', 'done']);
  });

  it('stops reading after done and ignores whatever follows', async () => {
    const events = await collect(
      streamFromChunks([frame('done', DONE_PAYLOAD), frame('token', { text: 'late' })])
    );

    expect(events).toEqual([{ type: 'done', response: DONE_PAYLOAD }]);
  });

  it('throws StreamIncompleteError for a body cut after one token', async () => {
    const consumed: AssistantSseEvent[] = [];

    await expect(
      (async () => {
        for await (const event of readAssistantSseStream(
          streamFromChunks([frame('token', { text: 'Hi' })])
        )) {
          consumed.push(event);
        }
      })()
    ).rejects.toBeInstanceOf(StreamIncompleteError);

    expect(consumed).toEqual([{ type: 'token', text: 'Hi' }]);
  });

  it('throws StreamIncompleteError for an empty body', async () => {
    await expect(collect(streamFromChunks([]))).rejects.toBeInstanceOf(StreamIncompleteError);
  });

  it('throws StreamIncompleteError when the last event never got its blank line', async () => {
    await expect(
      collect(streamFromChunks(['event: done\ndata: ' + JSON.stringify(DONE_PAYLOAD) + '\n']))
    ).rejects.toBeInstanceOf(StreamIncompleteError);
  });

  it('cancels the reader and rethrows the AbortError when the signal aborts mid-stream', async () => {
    const controller = new AbortController();
    let cancelled = false;
    let sent = false;
    const body = new ReadableStream<Uint8Array>({
      pull(streamController) {
        if (!sent) {
          sent = true;
          streamController.enqueue(encoder.encode(frame('token', { text: 'Hi' })));
          return undefined;
        }
        return new Promise<void>(() => {});
      },
      cancel() {
        cancelled = true;
      },
    });

    const received: AssistantSseEvent[] = [];
    const run = (async () => {
      for await (const event of readAssistantSseStream(body, controller.signal)) {
        received.push(event);
        setTimeout(() => controller.abort(), 0);
      }
    })();

    await expect(run).rejects.toMatchObject({ name: 'AbortError' });
    expect(received).toEqual([{ type: 'token', text: 'Hi' }]);
    expect(cancelled).toBe(true);
  });

  it('throws the AbortError at once for a signal that is already aborted, without reading', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(collect(stalledBody(), controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('delivers no event buffered in the same chunk once the signal has aborted', async () => {
    const controller = new AbortController();
    const chunk =
      frame('token', { text: 'a' }) +
      frame('token', { text: 'b' }) +
      frame('token', { text: 'c' }) +
      frame('done', DONE_PAYLOAD);
    const received: AssistantSseEvent[] = [];

    const run = (async () => {
      for await (const event of readAssistantSseStream(streamFromChunks([chunk]), controller.signal)) {
        received.push(event);
        controller.abort();
      }
    })();

    await expect(run).rejects.toMatchObject({ name: 'AbortError' });
    expect(received).toEqual([{ type: 'token', text: 'a' }]);
  });

  it('throws the AbortError, not StreamIncompleteError, for a malformed block buffered behind a yielded token', async () => {
    const controller = new AbortController();
    const chunk = frame('token', { text: 'a' }) + 'event: token\ndata: {"text":\n\n';
    const received: AssistantSseEvent[] = [];

    const run = (async () => {
      for await (const event of readAssistantSseStream(streamFromChunks([chunk]), controller.signal)) {
        received.push(event);
        controller.abort();
      }
    })();

    await expect(run).rejects.toMatchObject({ name: 'AbortError' });
    expect(received).toEqual([{ type: 'token', text: 'a' }]);
  });

  it('cancels the source when the consumer stops iterating early', async () => {
    let cancelled = false;
    let index = 0;
    const chunks = [frame('token', { text: 'a' }), frame('token', { text: 'b' })];
    const body = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(encoder.encode(chunks[index++ % chunks.length]));
      },
      cancel() {
        cancelled = true;
      },
    });

    for await (const event of readAssistantSseStream(body)) {
      expect(event).toEqual({ type: 'token', text: 'a' });
      break;
    }

    expect(cancelled).toBe(true);
  });

  it('skips a block that has data but no event line', async () => {
    const events = await collect(
      streamFromChunks(['data: {"text":"orphan"}\n\n', frame('done', DONE_PAYLOAD)])
    );

    expect(events.map((event) => event.type)).toEqual(['done']);
  });

  it.each([
    ['token data that is not JSON', 'event: token\ndata: {"text":\n\n'],
    ['a token whose text is not a string', 'event: token\ndata: {"text":5}\n\n'],
    ['a token with no text', 'event: token\ndata: {}\n\n'],
    ['an error whose code is not a number', 'event: error\ndata: {"code":"503","detail":"x"}\n\n'],
    ['an error whose detail is not a string', 'event: error\ndata: {"code":503,"detail":7}\n\n'],
    ['a done whose payload is null', 'event: done\ndata: null\n\n'],
    ['a done whose payload is an array', 'event: done\ndata: []\n\n'],
    ['a done whose payload is an empty object', 'event: done\ndata: {}\n\n'],
    [
      'a done with no checks',
      `event: done\ndata: ${JSON.stringify({ ...DONE_PAYLOAD, checks: undefined })}\n\n`,
    ],
    [
      'a done whose checks lack a boolean flag',
      `event: done\ndata: ${JSON.stringify({ ...DONE_PAYLOAD, checks: { ...DONE_PAYLOAD.checks, numbers_grounded: 'yes' } })}\n\n`,
    ],
    [
      'a done whose sources is not an array',
      `event: done\ndata: ${JSON.stringify({ ...DONE_PAYLOAD, sources: {} })}\n\n`,
    ],
    [
      'a done whose timing is a string',
      `event: done\ndata: ${JSON.stringify({ ...DONE_PAYLOAD, timing: 'fast' })}\n\n`,
    ],
    ['a token block with no data line', 'event: token\n\n'],
    ['a done block with no data line', 'event: done\n\n'],
    ['an error block with no data line', 'event: error\n\n'],
  ])('throws StreamIncompleteError for %s', async (_label, block) => {
    // A valid done follows the bad block, so only the payload check can be what throws.
    await expect(
      collect(streamFromChunks([block, frame('done', DONE_PAYLOAD)]))
    ).rejects.toBeInstanceOf(StreamIncompleteError);
  });

  it('throws NetworkError with the cause when the body fails before any chunk', async () => {
    const failure = new Error('network reset');
    const body = new ReadableStream<Uint8Array>({
      pull(streamController) {
        streamController.error(failure);
      },
    });

    const error: unknown = await collect(body).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(NetworkError);
    expect((error as NetworkError).cause).toBe(failure);
  });

  it('throws NetworkError with the cause when the connection drops after a chunk was read', async () => {
    // A real stream whose pull rejects on its second call: the way fetch() surfaces a
    // connection lost mid-body, as a bare TypeError from reader.read().
    const failure = new TypeError('network error');
    let sent = false;
    const body = new ReadableStream<Uint8Array>({
      pull(streamController) {
        if (sent) return Promise.reject(failure);
        sent = true;
        streamController.enqueue(encoder.encode(frame('token', { text: 'Hi' })));
        return undefined;
      },
    });
    const received: AssistantSseEvent[] = [];

    const error: unknown = await (async () => {
      for await (const event of readAssistantSseStream(body)) received.push(event);
    })().catch((e: unknown) => e);

    expect(received).toEqual([{ type: 'token', text: 'Hi' }]);
    expect(error).toBeInstanceOf(NetworkError);
    expect((error as NetworkError).cause).toBe(failure);
  });

  it('throws NetworkError when a read fails and the signal that was passed has not aborted', async () => {
    const failure = new TypeError('network error');
    let sent = false;
    const body = new ReadableStream<Uint8Array>({
      pull(streamController) {
        if (sent) return Promise.reject(failure);
        sent = true;
        streamController.enqueue(encoder.encode(frame('token', { text: 'Hi' })));
        return undefined;
      },
    });

    const error: unknown = await collect(body, new AbortController().signal).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(NetworkError);
    expect((error as NetworkError).cause).toBe(failure);
  });

  it('throws the AbortError, not NetworkError, when an abort makes the pending read reject', async () => {
    const controller = new AbortController();
    const body = new ReadableStream<Uint8Array>({
      start(streamController) {
        // Registered before the reader's own listener, so the stream is already
        // errored when the reader cancels it.
        controller.signal.addEventListener('abort', () =>
          streamController.error(new TypeError('network error'))
        );
      },
      pull: () => new Promise<void>(() => {}),
    });

    const run = collect(body, controller.signal);
    controller.abort();

    await expect(run).rejects.toMatchObject({ name: 'AbortError' });
  });
});
