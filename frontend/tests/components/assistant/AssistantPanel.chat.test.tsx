import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { AssistantPanel } from '@/components/assistant/AssistantPanel';
import { AssistantUIProvider, useAssistantUI } from '@/contexts/AssistantUIContext';
import { HttpError } from '@/lib/errors';
import type { AssistantChatResponse } from '@/types/api';
import '@/components/assistant/i18n';

// The panel with the real hook behind it: only the network and the stream reader are replaced.
vi.mock('@/hooks/use-media-query', () => ({ useMediaQuery: () => true }));

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

function renderPanel(onOpenChange = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AssistantPanel open onOpenChange={onOpenChange} projectId={null} userId="u1" mode="workflow" />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return onOpenChange;
}

const box = () => screen.getByRole('textbox', { name: 'Ask a question…' });

describe('AssistantPanel with the chat hook', () => {
  beforeEach(() => {
    mockStream.mockReset();
    mockRead.mockReset();
    window.sessionStorage.clear();
    mockStream.mockResolvedValue({ body: {} } as Response);
    mockRead.mockImplementation(async function* () {
      yield { type: 'done', response: RESPONSE };
    });
  });

  it('sends the typed question on Enter and shows the question and the answer', async () => {
    renderPanel();

    await userEvent.type(box(), 'What is it?{Enter}');

    await waitFor(() => expect(screen.getByText(RESPONSE.answer)).toBeInTheDocument());
    expect(screen.getByRole('log')).toHaveTextContent('What is it?');
    expect(box()).toHaveValue('');
    expect(mockStream.mock.calls[0][0]).toMatchObject({ message: 'What is it?', project_id: null });
  });

  it('puts a refused question back in the box and re-sends that very question on Try again', async () => {
    mockStream.mockRejectedValueOnce(new HttpError('Service Unavailable', 503));
    renderPanel();
    await userEvent.type(box(), 'Why?{Enter}');
    await waitFor(() => expect(box()).toHaveValue('Why?'));
    await userEvent.clear(box());
    await userEvent.type(box(), 'a different draft');

    await userEvent.click(await screen.findByRole('button', { name: 'Try again' }));

    await waitFor(() => expect(screen.getByText(RESPONSE.answer)).toBeInTheDocument());
    expect(mockStream.mock.calls[1][0]).toMatchObject({ message: 'Why?' });
    expect(box()).toHaveValue('a different draft');
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  });

  it('keeps the sheet open on Escape while the answer is on its way, and stops it with Stop', async () => {
    mockRead.mockImplementation(async function* (_body: unknown, signal: AbortSignal) {
      await new Promise((_resolve, reject) =>
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      );
      yield { type: 'done', response: RESPONSE };
    });
    const onOpenChange = renderPanel();
    await userEvent.type(box(), 'Slow one{Enter}');
    await screen.findByRole('button', { name: 'Stop' });

    await userEvent.keyboard('{Escape}');
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Stop' }));
    await waitFor(() => expect(screen.getByText('Stopped')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument();
  });
});

describe('closing the panel with a turn in flight', () => {
  // What AssistantRoot does: the panel is mounted for good, and open and project come from the context.
  function Mounted() {
    const { isOpen, projectId, openAssistant, closeAssistant } = useAssistantUI();
    return (
      <>
        <button onClick={() => openAssistant('p1')}>open</button>
        <button onClick={closeAssistant}>close</button>
        <AssistantPanel open={isOpen} onOpenChange={() => undefined} projectId={projectId} userId="u1" mode="workflow" />
      </>
    );
  }

  beforeEach(() => {
    mockStream.mockReset();
    mockRead.mockReset();
    window.sessionStorage.clear();
    mockStream.mockResolvedValue({ body: {} } as Response);
  });

  it('keeps streaming, and the answer is there when the panel is opened again', async () => {
    let release: (() => void) | undefined;
    let aborted = false;
    mockRead.mockImplementation(async function* (_body: unknown, signal: AbortSignal) {
      signal.addEventListener('abort', () => {
        aborted = true;
      });
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      yield { type: 'done', response: RESPONSE };
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AssistantUIProvider>
            <Mounted />
          </AssistantUIProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
    await userEvent.click(screen.getByText('open'));
    await userEvent.type(box(), 'Slow one{Enter}');
    await screen.findByRole('button', { name: 'Stop' });

    await userEvent.click(screen.getByText('close'));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    release?.();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await userEvent.click(screen.getByText('open'));

    expect(aborted).toBe(false);
    expect(await screen.findByText(RESPONSE.answer)).toBeInTheDocument();
    expect(screen.getByRole('log')).toHaveTextContent('Slow one');
  });
});
