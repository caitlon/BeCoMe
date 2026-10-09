import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useAssistantConfig } from '@/components/assistant/useAssistantConfig';
import { HttpError } from '@/lib/errors';

const mockGetAssistantConfig = vi.fn();
vi.mock('@/components/assistant/assistant-api', () => ({
  getAssistantConfig: () => mockGetAssistantConfig(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useAssistantConfig', () => {
  it('returns the config on success', async () => {
    mockGetAssistantConfig.mockResolvedValueOnce({
      enabled: true, model: 'Qwen/Qwen3-4B-Instruct-2507', mode: 'hybrid', collection: 'docs_default',
    });

    const { result } = renderHook(() => useAssistantConfig(true), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.model).toBe('Qwen/Qwen3-4B-Instruct-2507');
  });

  it('does not retry a 404 and settles as an error', async () => {
    mockGetAssistantConfig.mockRejectedValue(new HttpError('Not Found', 404));

    const { result } = renderHook(() => useAssistantConfig(true), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(mockGetAssistantConfig).toHaveBeenCalledTimes(1);
  });

  it('does not fetch when disabled', () => {
    renderHook(() => useAssistantConfig(false), { wrapper });

    expect(mockGetAssistantConfig).not.toHaveBeenCalled();
  });
});
