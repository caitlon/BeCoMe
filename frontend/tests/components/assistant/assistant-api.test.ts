import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getAssistantConfig, streamAssistantMessage } from '@/components/assistant/assistant-api';
import { HttpError, ServerError } from '@/lib/errors';
import type { AssistantChatRequest } from '@/types/api';

const mockRequestJson = vi.fn();
const mockRequestStream = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    requestJson: (...args: unknown[]) => mockRequestJson(...args),
    requestStream: (...args: unknown[]) => mockRequestStream(...args),
  },
}));

describe('assistant-api', () => {
  beforeEach(() => {
    mockRequestJson.mockReset();
    mockRequestStream.mockReset();
  });

  describe('getAssistantConfig', () => {
    it('requests the config path with no body', async () => {
      mockRequestJson.mockResolvedValueOnce({
        enabled: true,
        model: 'Qwen/Qwen3-4B-Instruct-2507',
        mode: 'hybrid',
        collection: 'docs_default',
        answer_provider: 'local',
        query_provider: 'local',
        embedding_provider: 'local',
      });

      const config = await getAssistantConfig();

      expect(config.model).toBe('Qwen/Qwen3-4B-Instruct-2507');
      expect(mockRequestJson).toHaveBeenCalledWith('/assistant/config');
    });

    it('propagates a rejection from requestJson unchanged', async () => {
      mockRequestJson.mockRejectedValueOnce(new HttpError('Not Found', 404));

      await expect(getAssistantConfig()).rejects.toBeInstanceOf(HttpError);
    });
  });

  describe('streamAssistantMessage', () => {
    const request: AssistantChatRequest = { message: 'hi', history: [], project_id: null, locale: 'en' };

    it('POSTs to the stream path with Accept: text/event-stream and the abort signal', async () => {
      const controller = new AbortController();
      const stream = new ReadableStream();
      mockRequestStream.mockResolvedValueOnce({ body: stream } as Response);

      const response = await streamAssistantMessage(request, controller.signal);

      expect(response.body).toBe(stream);
      expect(mockRequestStream).toHaveBeenCalledWith('/assistant/chat/stream', {
        method: 'POST',
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
        body: JSON.stringify(request),
      });
    });

    it('propagates a rejection from requestStream unchanged', async () => {
      mockRequestStream.mockRejectedValueOnce(new ServerError('Service Unavailable', 503));

      await expect(streamAssistantMessage(request, new AbortController().signal)).rejects.toMatchObject({
        status: 503,
      });
    });

    it('lets an aborted signal reject the call with the AbortError', async () => {
      const controller = new AbortController();
      const abortError = new DOMException('Aborted', 'AbortError');
      mockRequestStream.mockImplementation(
        (_endpoint: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            (init.signal as AbortSignal).addEventListener('abort', () => reject(abortError));
          })
      );

      const promise = streamAssistantMessage(request, controller.signal);
      controller.abort();

      await expect(promise).rejects.toBe(abortError);
    });
  });
});
