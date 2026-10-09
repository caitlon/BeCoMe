import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import i18n from '@/i18n';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { AssistantPanel } from '@/components/assistant/AssistantPanel';
import '@/components/assistant/i18n';

let mockIsDesktop = true;
vi.mock('@/hooks/use-media-query', () => ({ useMediaQuery: () => mockIsDesktop }));

function renderPanel(props: Partial<React.ComponentProps<typeof AssistantPanel>> = {}, seededName?: string) {
  const client = new QueryClient();
  if (seededName) client.setQueryData(queryKeys.project('p1'), { id: 'p1', name: seededName });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const onOpenChange = vi.fn();
  render(<AssistantPanel open onOpenChange={onOpenChange} projectId={null} {...props} />, { wrapper });
  return { onOpenChange, client };
}

function OpenerHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>opener</button>
      <button>elsewhere</button>
      <AssistantPanel open={open} onOpenChange={setOpen} projectId={null} />
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
        <AssistantPanel open onOpenChange={vi.fn()} projectId="p1" />
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

  it('hands the clicked suggestion to onSuggestion', async () => {
    const onSuggestion = vi.fn();
    renderPanel({ onSuggestion });

    await userEvent.click(screen.getByRole('button', { name: 'How do I invite experts?' }));

    expect(onSuggestion).toHaveBeenCalledWith('How do I invite experts?');
  });

  it('ignores a suggestion click when no handler is given', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'How do I invite experts?' }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('renders the composer and the clear button disabled', () => {
    renderPanel();

    expect(screen.getByRole('textbox', { name: 'Ask a question…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Clear conversation' })).toBeDisabled();
    expect(screen.getByText('0 / 4000')).toBeInTheDocument();
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
