import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { focusManager, onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useAssistantConfig } from '@/components/assistant/useAssistantConfig';
import { HttpError, NetworkError, ServerError } from '@/lib/errors';

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
    onlineManager.setOnline(true);
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

  describe('a transient failure', () => {
    const config = { enabled: true, model: 'm', mode: 'hybrid', collection: 'c' };

    // Default retry policy with no backoff, so the retries run inside the test.
    function sharedClient() {
      const client = new QueryClient({ defaultOptions: { queries: { retryDelay: 0 } } });
      const sharedClientWrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      );
      return sharedClientWrapper;
    }

    async function regainFocus() {
      // The client refetches on focus from an async listener, so let it run.
      await act(async () => {
        focusManager.setFocused(false);
        focusManager.setFocused(true);
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }

    it('is retried when the server answers 502 and recovers', async () => {
      mockGetAssistantConfig
        .mockRejectedValueOnce(new ServerError('Bad Gateway', 502))
        .mockResolvedValueOnce(config);

      const { result } = renderHook(() => useAssistantConfig(true), { wrapper: sharedClient() });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockGetAssistantConfig).toHaveBeenCalledTimes(2);
    });

    it('is retried when the network fails and recovers', async () => {
      mockGetAssistantConfig
        .mockRejectedValueOnce(new NetworkError())
        .mockResolvedValueOnce(config);

      const { result } = renderHook(() => useAssistantConfig(true), { wrapper: sharedClient() });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockGetAssistantConfig).toHaveBeenCalledTimes(2);
    });

    it('is requested again on window focus once the retries are spent', async () => {
      mockGetAssistantConfig
        .mockRejectedValueOnce(new ServerError('Bad Gateway', 502))
        .mockRejectedValueOnce(new ServerError('Bad Gateway', 502))
        .mockRejectedValueOnce(new ServerError('Bad Gateway', 502))
        .mockResolvedValueOnce(config);

      const { result } = renderHook(() => useAssistantConfig(true), { wrapper: sharedClient() });
      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(mockGetAssistantConfig).toHaveBeenCalledTimes(3);

      await regainFocus();

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockGetAssistantConfig).toHaveBeenCalledTimes(4);
    });

    it('is requested again when the connection comes back', async () => {
      mockGetAssistantConfig
        .mockRejectedValueOnce(new NetworkError())
        .mockRejectedValueOnce(new NetworkError())
        .mockRejectedValueOnce(new NetworkError())
        .mockResolvedValueOnce(config);

      const { result } = renderHook(() => useAssistantConfig(true), { wrapper: sharedClient() });
      await waitFor(() => expect(result.current.isError).toBe(true));

      await act(async () => {
        onlineManager.setOnline(false);
        onlineManager.setOnline(true);
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockGetAssistantConfig).toHaveBeenCalledTimes(4);
    });

    it('is requested again when the hook remounts', async () => {
      mockGetAssistantConfig
        .mockRejectedValueOnce(new ServerError('Bad Gateway', 502))
        .mockRejectedValueOnce(new ServerError('Bad Gateway', 502))
        .mockRejectedValueOnce(new ServerError('Bad Gateway', 502))
        .mockResolvedValueOnce(config);
      const wrapperForBoth = sharedClient();

      const first = renderHook(() => useAssistantConfig(true), { wrapper: wrapperForBoth });
      await waitFor(() => expect(first.result.current.isError).toBe(true));
      first.unmount();

      const second = renderHook(() => useAssistantConfig(true), { wrapper: wrapperForBoth });
      await waitFor(() => expect(second.result.current.isSuccess).toBe(true));
      expect(mockGetAssistantConfig).toHaveBeenCalledTimes(4);
    });
  });

  it('does not request again on focus or reconnect after a success', async () => {
    mockGetAssistantConfig.mockResolvedValue({
      enabled: true, model: 'm', mode: 'hybrid', collection: 'c',
    });
    const client = new QueryClient();
    const sharedClientWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useAssistantConfig(true), { wrapper: sharedClientWrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await act(async () => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
      onlineManager.setOnline(false);
      onlineManager.setOnline(true);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(mockGetAssistantConfig).toHaveBeenCalledTimes(1);
  });

  it('does not request again when the connection comes back after a 404', async () => {
    mockGetAssistantConfig.mockRejectedValue(new HttpError('Not Found', 404));
    const client = new QueryClient();
    const sharedClientWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useAssistantConfig(true), { wrapper: sharedClientWrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));

    await act(async () => {
      onlineManager.setOnline(false);
      onlineManager.setOnline(true);
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
