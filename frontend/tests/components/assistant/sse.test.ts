import { describe, it, expect } from 'vitest';
import { readAssistantSseStream } from '@/components/assistant/sse';
import type { AssistantSseEvent } from '@/components/assistant/sse';
import { StreamIncompleteError } from '@/lib/errors';

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
    const euro = bytes.indexOf(0xc5); // first byte of a two-byte letter
    const events = await collect(streamFromChunks([bytes.slice(0, euro + 1), bytes.slice(euro + 1)]));

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

  it('throws the AbortError at once for a signal that is already aborted', async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(
      collect(streamFromChunks([frame('done', DONE_PAYLOAD)]), controller.signal)
    ).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('lets a failure of the underlying body reach the caller', async () => {
    const failure = new Error('network reset');
    const body = new ReadableStream<Uint8Array>({
      pull(streamController) {
        streamController.error(failure);
      },
    });

    await expect(collect(body)).rejects.toBe(failure);
  });
});
