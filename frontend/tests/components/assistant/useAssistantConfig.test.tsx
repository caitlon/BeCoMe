import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
  beforeEach(() => {
    mockGetAssistantConfig.mockReset();
  });

  afterEach(() => {
    focusManager.setFocused(undefined);
  });

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

  it('does not retry a 404 under the default retry policy', async () => {
    mockGetAssistantConfig.mockReset();
    mockGetAssistantConfig.mockRejectedValue(new HttpError('Not Found', 404));
    // The shared wrapper turns retries off for every query, which would hide a
    // missing `retry: false` in the hook itself; this client keeps the defaults.
    const client = new QueryClient();
    const defaultRetryWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useAssistantConfig(true), { wrapper: defaultRetryWrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(mockGetAssistantConfig).toHaveBeenCalledTimes(1);
  });

  it('does not request again when the hook remounts after a 404', async () => {
    mockGetAssistantConfig.mockReset();
    mockGetAssistantConfig.mockRejectedValue(new HttpError('Not Found', 404));
    const client = new QueryClient();
    const sharedClientWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const first = renderHook(() => useAssistantConfig(true), { wrapper: sharedClientWrapper });
    await waitFor(() => expect(first.result.current.isError).toBe(true));
    first.unmount();

    const second = renderHook(() => useAssistantConfig(true), { wrapper: sharedClientWrapper });
    await waitFor(() => expect(second.result.current.isError).toBe(true));

    expect(mockGetAssistantConfig).toHaveBeenCalledTimes(1);
  });

  it('does not request again when the window regains focus after a 404', async () => {
    mockGetAssistantConfig.mockRejectedValue(new HttpError('Not Found', 404));
    const client = new QueryClient();
    const sharedClientWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useAssistantConfig(true), { wrapper: sharedClientWrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));

    // The client refetches on focus from an async listener, so let it run.
    await act(async () => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(mockGetAssistantConfig).toHaveBeenCalledTimes(1);
  });

  it('does not request again when the hook remounts after a success', async () => {
    mockGetAssistantConfig.mockResolvedValue({
      enabled: true, model: 'm', mode: 'hybrid', collection: 'c',
    });
    const client = new QueryClient();
    const sharedClientWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const first = renderHook(() => useAssistantConfig(true), { wrapper: sharedClientWrapper });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    first.unmount();

    const second = renderHook(() => useAssistantConfig(true), { wrapper: sharedClientWrapper });
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true));

    expect(mockGetAssistantConfig).toHaveBeenCalledTimes(1);
  });
});
