import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getAssistantConfig } from '@/components/assistant/assistant-api';
import { HttpError } from '@/lib/errors';

const mockRequestJson = vi.fn();
vi.mock('@/lib/api', () => ({
  api: { requestJson: (...args: unknown[]) => mockRequestJson(...args) },
}));

describe('assistant-api', () => {
  beforeEach(() => {
    mockRequestJson.mockReset();
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
});
