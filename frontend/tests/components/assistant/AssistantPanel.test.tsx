import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import i18n from '@/i18n';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { AssistantPanel } from '@/components/assistant/AssistantPanel';
import type { AssistantMessage } from '@/components/assistant/useAssistantChat';
import '@/components/assistant/i18n';

let mockIsDesktop = true;
vi.mock('@/hooks/use-media-query', () => ({ useMediaQuery: () => mockIsDesktop }));

// The hook has its own tests; here it is a script, so the panel's wiring and its
// pending and confirmation states can be set up without a stream.
const mockUseAssistantChat = vi.fn();
vi.mock('@/components/assistant/useAssistantChat', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/components/assistant/useAssistantChat')>()),
  useAssistantChat: (...args: unknown[]) => mockUseAssistantChat(...args),
}));

const answered: AssistantMessage[] = [
  { id: 'm1', role: 'user', content: 'Why?', status: 'done', createdAt: 1 },
  { id: 'm2', role: 'assistant', content: 'Because.', status: 'done', createdAt: 1 },
];

let chat: ReturnType<typeof makeChat>;
function makeChat(overrides: Record<string, unknown> = {}) {
  return {
    messages: [] as AssistantMessage[],
    draft: '',
    setDraft: vi.fn(),
    sendMessage: vi.fn(),
    retry: vi.fn(),
    cancel: vi.fn(),
    clear: vi.fn(),
    isPending: false,
    pendingSeconds: 0,
    startedAt: null,
    historyWindowStart: -1,
    ...overrides,
  };
}

function renderPanel(props: Partial<React.ComponentProps<typeof AssistantPanel>> = {}, seededName?: string) {
  const client = new QueryClient();
  if (seededName) client.setQueryData(queryKeys.project('p1'), { id: 'p1', name: seededName });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const onOpenChange = vi.fn();
  render(<AssistantPanel open onOpenChange={onOpenChange} projectId={null} userId="u1" mode="workflow" {...props} />, {
    wrapper,
  });
  return { onOpenChange, client };
}

function OpenerHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>opener</button>
      <button>elsewhere</button>
      <AssistantPanel open={open} onOpenChange={setOpen} projectId={null} userId="u1" mode="workflow" />
    </>
  );
}

function renderHarness() {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <OpenerHarness />
    </QueryClientProvider>
  );
}

describe('AssistantPanel', () => {
  beforeEach(() => {
    mockIsDesktop = true;
    chat = makeChat();
    mockUseAssistantChat.mockImplementation(() => chat);
  });

  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('has an accessible title and a description naming the scope', () => {
    renderPanel();

    const dialog = screen.getByRole('dialog', { name: 'Assistant' });
    expect(dialog).toHaveAccessibleDescription('Method and app');
  });

  it('shows the project name from the cache when scoped, without fetching', () => {
    const getProject = vi.spyOn(api, 'getProject');

    renderPanel({ projectId: 'p1' }, 'Flood prevention');

    expect(screen.getByRole('dialog')).toHaveAccessibleDescription('Project “Flood prevention”');
    expect(screen.getByText('Ask about this project')).toBeInTheDocument();
    expect(getProject).not.toHaveBeenCalled();
  });

  it('shows the three project suggestions when a project is open', () => {
    renderPanel({ projectId: 'p1' }, 'Flood prevention');

    for (const text of [
      'What does the result mean?',
      'Why is the confidence moderate?',
      'How is the best compromise computed?',
    ]) {
      expect(screen.getByRole('button', { name: text })).toBeInTheDocument();
    }
    expect(screen.queryByRole('button', { name: 'What is a fuzzy opinion?' })).not.toBeInTheDocument();
  });

  it('leaves the project page able to refetch the shared project query while it is open', async () => {
    const getProject = vi.spyOn(api, 'getProject').mockResolvedValue({ id: 'p1', name: 'Renamed' } as never);
    // The app's staleTime, so mounting the page observer does not itself refetch;
    // no retries, because a retry would pick up the page's queryFn and mask the failure.
    const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false } } });
    client.setQueryData(queryKeys.project('p1'), { id: 'p1', name: 'Old name' });
    // Stands in for ProjectDetail: an active observer of the same key with the real fetcher.
    function ProjectPage() {
      useQuery({ queryKey: queryKeys.project('p1'), queryFn: () => api.getProject('p1') });
      return null;
    }
    render(
      <QueryClientProvider client={client}>
        <ProjectPage />
        <AssistantPanel open onOpenChange={vi.fn()} projectId="p1" userId="u1" mode="workflow" />
      </QueryClientProvider>
    );
    expect(screen.getByRole('dialog')).toHaveAccessibleDescription('Project “Old name”');

    await client.invalidateQueries({ queryKey: queryKeys.project('p1') });

    expect(getProject).toHaveBeenCalledTimes(1);
    expect(client.getQueryState(queryKeys.project('p1'))?.status).toBe('success');
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveAccessibleDescription('Project “Renamed”'));
  });

  it('creates no query entry at all when there is no project', () => {
    const { client } = renderPanel();

    expect(client.getQueryCache().getAll()).toEqual([]);
  });

  it('falls back to the generic subtitle while the project name is not cached', () => {
    renderPanel({ projectId: 'p1' });

    expect(screen.getByRole('dialog')).toHaveAccessibleDescription('Method and app');
    expect(screen.getByText('What does the result mean?')).toBeInTheDocument();
  });

  it('shows the general empty state and suggestions with no project', () => {
    renderPanel();

    expect(screen.getByText('Ask about the method or the app')).toBeInTheDocument();
    expect(screen.getByText('Sees only what you see in this project.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'What is a fuzzy opinion?' })).toBeInTheDocument();
    expect(screen.getByText('The assistant can be wrong. Check the result page.')).toBeInTheDocument();
  });

  it('fills the draft with the clicked suggestion and focuses the box', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'How do I invite experts?' }));

    expect(chat.setDraft).toHaveBeenCalledWith('How do I invite experts?');
    expect(screen.getByRole('textbox', { name: 'Ask a question…' })).toHaveFocus();
    expect(chat.sendMessage).not.toHaveBeenCalled();
  });

  it('puts the focus in the question box when the panel opens', async () => {
    renderPanel();

    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Ask a question…' })).toHaveFocus());
  });

  it('keeps the conversation for the signed-in user and the open project', () => {
    renderPanel({ projectId: 'p1', userId: 'user-7' });

    expect(mockUseAssistantChat).toHaveBeenCalledWith({ projectId: 'p1', userId: 'user-7' });
  });

  describe('composer wiring', () => {
    it('shows the draft, with its length against the limit', () => {
      chat = makeChat({ draft: 'hello' });
      renderPanel();

      expect(screen.getByRole('textbox', { name: 'Ask a question…' })).toHaveValue('hello');
      expect(screen.getByText('5 / 4000')).toBeInTheDocument();
    });

    it('stores what is typed, and sends on Enter', async () => {
      chat = makeChat({ draft: 'hello' });
      renderPanel();

      await userEvent.type(screen.getByRole('textbox', { name: 'Ask a question…' }), '!{Enter}');

      expect(chat.setDraft).toHaveBeenCalledWith('hello!');
      expect(chat.sendMessage).toHaveBeenCalledTimes(1);
    });

    it('turns Send into Stop while a turn is pending, and Stop cancels', async () => {
      chat = makeChat({ messages: [answered[0]], isPending: true });
      renderPanel();

      await userEvent.click(screen.getByRole('button', { name: 'Stop' }));

      expect(chat.cancel).toHaveBeenCalledTimes(1);
    });
  });

  describe('conversation', () => {
    it('shows the feed instead of the empty state once there are messages', () => {
      chat = makeChat({ messages: answered });
      renderPanel();

      expect(screen.getByRole('log', { name: 'Conversation' })).toHaveTextContent('Because.');
      expect(screen.queryByText('Ask about the method or the app')).not.toBeInTheDocument();
    });

    it('hands the feed the retry of the hook', async () => {
      chat = makeChat({
        messages: [
          answered[0],
          { id: 'm3', role: 'assistant', content: '', status: 'error', error: { code: 503, detail: 'x' }, createdAt: 2 },
        ],
      });
      renderPanel();

      await userEvent.click(screen.getByRole('button', { name: 'Try again' }));

      expect(chat.retry).toHaveBeenCalledWith('Why?');
    });

    it('hands the feed the mode: a hybrid answer in flight shows a phase, not a cursor', () => {
      chat = makeChat({
        messages: [answered[0], { id: 'm3', role: 'assistant', content: '', status: 'pending', createdAt: 2 }],
        isPending: true,
      });
      renderPanel({ mode: 'hybrid' });

      expect(within(screen.getByRole('log')).getByText('Searching the documentation…')).toBeInTheDocument();
    });

    it('tells the feed whether the conversation is about a project: no reading phase without one', () => {
      chat = makeChat({
        messages: [answered[0], { id: 'm3', role: 'assistant', content: '', status: 'pending', createdAt: 2 }],
        isPending: true,
        pendingSeconds: 4,
      });
      const { unmount } = render(
        <QueryClientProvider client={new QueryClient()}>
          <AssistantPanel open onOpenChange={vi.fn()} projectId="p1" userId="u1" mode="hybrid" />
        </QueryClientProvider>
      );
      expect(within(screen.getByRole('log')).getByText('Reading the project…')).toBeInTheDocument();
      unmount();

      renderPanel({ mode: 'hybrid' });

      expect(within(screen.getByRole('log')).getByText('Searching the documentation…')).toBeInTheDocument();
    });

    it('does not announce the old failure of another conversation as new when the thread swaps', () => {
      chat = makeChat({ messages: answered });
      const client = new QueryClient();
      const ui = (projectId: string | null) => (
        <QueryClientProvider client={client}>
          <AssistantPanel open onOpenChange={vi.fn()} projectId={projectId} userId="u1" mode="workflow" />
        </QueryClientProvider>
      );
      const { rerender } = render(ui('p1'));

      chat = makeChat({
        messages: [
          { id: 'g1', role: 'user', content: 'Old?', status: 'error', createdAt: 1 },
          { id: 'g2', role: 'assistant', content: '', status: 'error', error: { code: 503, detail: 'x' }, createdAt: 1 },
        ],
      });
      rerender(ui(null));

      expect(screen.getByText('The assistant is temporarily unavailable.')).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('clearing', () => {
    it('keeps the clear button disabled while there is nothing to clear', () => {
      renderPanel();

      expect(screen.getByRole('button', { name: 'Clear conversation' })).toBeDisabled();
    });

    it('keeps the clear button disabled while a turn is pending', () => {
      chat = makeChat({ messages: answered, isPending: true });
      renderPanel();

      expect(screen.getByRole('button', { name: 'Clear conversation' })).toBeDisabled();
    });

    it('asks inline first, and clears nothing before the answer', async () => {
      chat = makeChat({ messages: answered });
      renderPanel();

      await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }));

      expect(screen.getByRole('group', { name: 'Clear the conversation? This cannot be undone.' })).toBeInTheDocument();
      expect(screen.getAllByRole('dialog')).toHaveLength(1);
      expect(chat.clear).not.toHaveBeenCalled();
      expect(screen.getByRole('button', { name: 'Keep' })).toHaveFocus();
    });

    it('clears on confirmation and moves focus to the box', async () => {
      chat = makeChat({ messages: answered });
      renderPanel();
      await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }));

      await userEvent.click(screen.getByRole('button', { name: 'Clear' }));

      expect(chat.clear).toHaveBeenCalledTimes(1);
      expect(screen.queryByRole('button', { name: 'Keep' })).not.toBeInTheDocument();
      expect(screen.getByRole('textbox', { name: 'Ask a question…' })).toHaveFocus();
    });

    it('backs out on Keep and returns focus to the clear button', async () => {
      chat = makeChat({ messages: answered });
      renderPanel();
      await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }));

      await userEvent.click(screen.getByRole('button', { name: 'Keep' }));

      expect(chat.clear).not.toHaveBeenCalled();
      expect(screen.queryByRole('button', { name: 'Keep' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Clear conversation' })).toHaveFocus();
    });

    it('backs out on Escape without closing the sheet, and the next Escape closes it', async () => {
      chat = makeChat({ messages: answered });
      const { onOpenChange } = renderPanel();
      await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }));

      await userEvent.keyboard('{Escape}');

      expect(screen.queryByRole('button', { name: 'Keep' })).not.toBeInTheDocument();
      expect(onOpenChange).not.toHaveBeenCalled();
      expect(chat.clear).not.toHaveBeenCalled();

      await userEvent.keyboard('{Escape}');
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it('drops the confirmation when the sheet is closed, and it is not there when reopened', async () => {
      chat = makeChat({ messages: answered });
      const client = new QueryClient();
      const ui = (open: boolean, projectId: string | null = null) => (
        <QueryClientProvider client={client}>
          <AssistantPanel open={open} onOpenChange={vi.fn()} projectId={projectId} userId="u1" mode="workflow" />
        </QueryClientProvider>
      );
      const { rerender } = render(ui(true));
      await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }));
      expect(screen.getByRole('button', { name: 'Keep' })).toBeInTheDocument();

      rerender(ui(false));
      rerender(ui(true));

      expect(screen.queryByRole('button', { name: 'Keep' })).not.toBeInTheDocument();
    });

    it('does not carry the confirmation over to another conversation', async () => {
      chat = makeChat({ messages: answered });
      const client = new QueryClient();
      const ui = (projectId: string | null) => (
        <QueryClientProvider client={client}>
          <AssistantPanel open onOpenChange={vi.fn()} projectId={projectId} userId="u1" mode="workflow" />
        </QueryClientProvider>
      );
      const { rerender } = render(ui('p1'));
      await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }));
      expect(screen.getByRole('button', { name: 'Keep' })).toBeInTheDocument();

      rerender(ui(null));

      expect(screen.queryByRole('button', { name: 'Keep' })).not.toBeInTheDocument();
    });

    it('drops the confirmation when a turn starts under it, and does not bring it back', async () => {
      chat = makeChat({ messages: answered });
      const client = new QueryClient();
      const ui = () => (
        <QueryClientProvider client={client}>
          <AssistantPanel open onOpenChange={vi.fn()} projectId={null} userId="u1" mode="workflow" />
        </QueryClientProvider>
      );
      const { rerender } = render(ui());
      await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }));
      expect(screen.getByRole('button', { name: 'Keep' })).toBeInTheDocument();

      chat = makeChat({ messages: answered, isPending: true });
      rerender(ui());
      expect(screen.queryByRole('button', { name: 'Keep' })).not.toBeInTheDocument();

      chat = makeChat({ messages: answered });
      rerender(ui());
      expect(screen.queryByRole('button', { name: 'Keep' })).not.toBeInTheDocument();
    });
  });

  describe('Escape while a turn is pending', () => {
    it('neither closes the sheet nor cancels the turn', async () => {
      chat = makeChat({ messages: [answered[0]], isPending: true });
      const { onOpenChange } = renderPanel();

      await userEvent.keyboard('{Escape}');

      expect(onOpenChange).not.toHaveBeenCalled();
      expect(chat.cancel).not.toHaveBeenCalled();
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('still lets the close button close it', async () => {
      chat = makeChat({ messages: [answered[0]], isPending: true });
      const { onOpenChange } = renderPanel();

      await userEvent.click(screen.getByRole('button', { name: 'Close' }));

      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('closes through its close button and on Escape', async () => {
    const { onOpenChange } = renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onOpenChange).toHaveBeenLastCalledWith(false);

    onOpenChange.mockClear();
    await userEvent.keyboard('{Escape}');
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('does not close on a click outside, and leaves the page interactive on desktop', async () => {
    const pageClick = vi.fn();
    render(<button onClick={pageClick}>page button</button>);
    const { onOpenChange } = renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'page button' }));

    expect(pageClick).toHaveBeenCalledTimes(1);
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it.each([['desktop', true], ['mobile', false]])(
    'gives focus back to the opener on close, on %s',
    async (_name, isDesktop) => {
      mockIsDesktop = isDesktop;
      renderHarness();
      const opener = screen.getByRole('button', { name: 'opener' });

      await userEvent.click(opener);
      await screen.findByRole('dialog');
      expect(opener).not.toHaveFocus();

      await userEvent.keyboard('{Escape}');

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
      await waitFor(() => expect(opener).toHaveFocus());
    }
  );

  it('does not pull focus back when the user moved it elsewhere on the page', async () => {
    renderHarness();
    await userEvent.click(screen.getByRole('button', { name: 'opener' }));
    await screen.findByRole('dialog');
    const elsewhere = screen.getByRole('button', { name: 'elsewhere' });

    await userEvent.click(elsewhere);
    await userEvent.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(elsewhere).toHaveFocus();
  });

  it('is a bottom sheet below the md breakpoint', () => {
    mockIsDesktop = false;
    renderPanel();

    expect(screen.getByRole('dialog').className).toContain('h-[94dvh]');
    expect(screen.getByRole('dialog').className).toContain('inset-x-0');
  });

  it('is a side sheet on desktop', () => {
    renderPanel();

    expect(screen.getByRole('dialog').className).toContain('sm:max-w-[440px]');
  });

  it('renders nothing when closed', () => {
    renderPanel({ open: false });

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('speaks Czech when the language is Czech', async () => {
    await i18n.changeLanguage('cs');
    renderPanel();

    expect(screen.getByRole('dialog', { name: 'Asistent' })).toBeInTheDocument();
    expect(screen.getByText('Zeptejte se na metodu nebo aplikaci')).toBeInTheDocument();
  });
});
