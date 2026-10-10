import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import AssistantRoot from '@/components/assistant/AssistantRoot';
import { AssistantUIProvider, useAssistantUI } from '@/contexts/AssistantUIContext';
import type { AssistantChatResponse } from '@/types/api';

// The real root, panel and hook; the session, the config, the network and the stream reader are replaced.
vi.mock('@/hooks/use-media-query', () => ({ useMediaQuery: () => true }));

type Auth = { isAuthenticated: boolean; status: string; user: { id: string } | null };
let mockAuth: Auth;
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
  registerSignOutListener: () => () => undefined,
}));
vi.mock('@/components/assistant/useAssistantConfig', () => ({
  useAssistantConfig: () => ({ isSuccess: true, data: { enabled: true, model: 'x', mode: 'workflow' } }),
}));

const mockStream = vi.fn();
vi.mock('@/components/assistant/assistant-api', () => ({
  streamAssistantMessage: (...args: unknown[]) => mockStream(...args),
}));
const mockRead = vi.fn();
vi.mock('@/components/assistant/sse', () => ({
  readAssistantSseStream: (...args: unknown[]) => mockRead(...args),
}));

const RESPONSE: AssistantChatResponse = {
  answer: 'The best compromise is the midpoint.',
  sources: [],
  tools_used: [],
  checks: { citations_valid: true, numbers_grounded: true, ungrounded_numbers: [] },
  usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2, llm_calls: 1, complete: true },
  timing: { ttft_ms: 1, total_ms: 2 },
};

const SIGNED_IN: Auth = { isAuthenticated: true, status: 'authenticated', user: { id: 'u1' } };

function Opener() {
  const { openAssistant } = useAssistantUI();
  return <button onClick={() => openAssistant()}>open</button>;
}

function Tree() {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AssistantUIProvider>
          <Opener />
          <AssistantRoot />
        </AssistantUIProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AssistantRoot while the session is re-read', () => {
  let aborted: boolean;
  let release: () => void;

  beforeEach(() => {
    mockAuth = SIGNED_IN;
    aborted = false;
    window.sessionStorage.clear();
    mockStream.mockReset();
    mockRead.mockReset();
    mockStream.mockResolvedValue({ body: {} } as Response);
    mockRead.mockImplementation(async function* (_body: unknown, signal: AbortSignal) {
      signal.addEventListener('abort', () => {
        aborted = true;
      });
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      yield { type: 'done', response: RESPONSE };
    });
  });

  async function startTurn() {
    const view = render(<Tree />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'open' })).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'open' }));
    await userEvent.type(await screen.findByRole('textbox', { name: 'Ask a question…' }), 'Slow one{Enter}');
    await screen.findByRole('button', { name: 'Stop' });
    return view;
  }

  it('does not abort a running turn on a reload of the same user, and the answer arrives', async () => {
    const view = await startTurn();

    mockAuth = { isAuthenticated: false, status: 'loading', user: { id: 'u1' } };
    view.rerender(<Tree />);
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
    mockAuth = SIGNED_IN;
    view.rerender(<Tree />);
    await act(async () => release());

    expect(aborted).toBe(false);
    expect(await screen.findByText(RESPONSE.answer)).toBeInTheDocument();
  });

  it('still takes the panel away, and aborts the turn, on a real sign-out', async () => {
    const view = await startTurn();

    mockAuth = { isAuthenticated: false, status: 'unauthenticated', user: null };
    view.rerender(<Tree />);

    await waitFor(() => expect(aborted).toBe(true));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
