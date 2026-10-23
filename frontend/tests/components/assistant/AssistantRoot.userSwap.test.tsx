import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import '@/i18n';
import AssistantRoot from '@/components/assistant/AssistantRoot';
import { STORAGE_PREFIX } from '@/components/assistant/useAssistantChat';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { AssistantUIProvider, useAssistantUI } from '@/contexts/AssistantUIContext';
import { queryKeys } from '@/lib/queryKeys';
import type { AssistantChatResponse } from '@/types/api';

// The real AuthProvider, root, panel and hook. Only the transport, the config and the media query are replaced.
vi.mock('@/hooks/use-media-query', () => ({ useMediaQuery: () => true }));

const mockGetCurrentUser = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    getCurrentUser: (...args: unknown[]) => mockGetCurrentUser(...args),
    setOnSessionExpired: () => undefined,
    login: vi.fn(),
    logout: vi.fn(),
  },
}));
vi.mock('@/components/assistant/useAssistantConfig', () => ({
  useAssistantConfig: () => ({ isSuccess: true, data: { enabled: true, model: 'x', mode: 'workflow' } }),
}));

// The real panel, wrapped to record the props of every render it gets.
const panelRenders = vi.hoisted(
  () => [] as { userId: string; open: boolean; projectId: string | null }[]
);
vi.mock('@/components/assistant/AssistantPanel', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/components/assistant/AssistantPanel')>();
  return {
    AssistantPanel: (props: React.ComponentProps<typeof original.AssistantPanel>) => {
      panelRenders.push({ userId: props.userId, open: props.open, projectId: props.projectId });
      return <original.AssistantPanel {...props} />;
    },
  };
});

// A turn is answered by a stream that finishes at once.
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

const USER_A = { id: 'user-a', email: 'a@example.com', first_name: 'A' };
const USER_B = { id: 'user-b', email: 'b@example.com', first_name: 'B' };

// What Profile (photo, name, password) and ServiceUnavailable's retry do after a write:
// re-read the session cookie. Another tab that signed A out and B in has swapped it.
function Harness() {
  const { refreshUser, login, logout, user } = useAuth();
  const { openAssistant, isOpen, projectId } = useAssistantUI();
  return (
    <>
      <button onClick={() => openAssistant('project-of-a')}>open</button>
      <button onClick={() => openAssistant(null)}>open general</button>
      <button onClick={() => void refreshUser()}>refresh</button>
      <button onClick={() => void login('b@example.com', 'pw')}>sign in</button>
      <button onClick={() => void logout()}>sign out</button>
      <output data-testid="ui">{JSON.stringify({ user: user?.id ?? null, isOpen, projectId })}</output>
    </>
  );
}

let queryClient: QueryClient;

function Tree() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>
          <AssistantUIProvider>
            <Harness />
            <AssistantRoot />
          </AssistantUIProvider>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

const STORED_A = `${STORAGE_PREFIX}:user-a:project-of-a`;
const STORED_B_GENERAL = `${STORAGE_PREFIX}:user-b:general`;
const BOX = { name: 'Ask a question…' };

async function openWithDraft() {
  await userEvent.click(await screen.findByRole('button', { name: 'open' }));
  const composer = await screen.findByRole('textbox', { name: 'Ask a question…' });
  await userEvent.type(composer, 'a private draft of A');
  expect(composer).toHaveValue('a private draft of A');
  expect(screen.getByTestId('ui')).toHaveTextContent('"projectId":"project-of-a"');
}

describe('AssistantRoot when the signed-in user changes with no sign-out event', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.sessionStorage.setItem(STORED_A, JSON.stringify([]));
    mockGetCurrentUser.mockReset();
    mockStream.mockReset();
    mockRead.mockReset();
    panelRenders.length = 0;
    mockStream.mockResolvedValue({ body: {} } as Response);
    mockRead.mockImplementation(async function* () {
      yield { type: 'done', response: RESPONSE };
    });
    queryClient = new QueryClient();
  });

  it("does not hand A's open panel, project, draft or stored conversations to B", async () => {
    mockGetCurrentUser.mockResolvedValueOnce(USER_A).mockResolvedValue(USER_B);
    render(<Tree />);
    await openWithDraft();

    // The session cookie now belongs to B; this tab never saw a sign-out.
    await userEvent.click(screen.getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":"user-b"'));

    expect(screen.getByTestId('ui')).toHaveTextContent('"isOpen":false');
    expect(screen.getByTestId('ui')).toHaveTextContent('"projectId":null');
    expect(screen.queryByDisplayValue('a private draft of A')).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem(STORED_A)).toBeNull();
  });

  it('resets nothing on the first sign-in or when the same user is re-read', async () => {
    mockGetCurrentUser.mockResolvedValue(USER_A);
    render(<Tree />);
    await openWithDraft();
    // Signing in (null -> A) did not clear what was already stored.
    expect(window.sessionStorage.getItem(STORED_A)).not.toBeNull();

    // refreshUser flips the status to loading and back with the same user.
    await userEvent.click(screen.getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(mockGetCurrentUser).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":"user-a"'));

    expect(screen.getByTestId('ui')).toHaveTextContent('"isOpen":true');
    expect(screen.getByTestId('ui')).toHaveTextContent('"projectId":"project-of-a"');
    expect(screen.getByRole('textbox', { name: 'Ask a question…' })).toHaveValue('a private draft of A');
    expect(window.sessionStorage.getItem(STORED_A)).not.toBeNull();
  });
  it("stores B's general conversation after the swap", async () => {
    mockGetCurrentUser.mockResolvedValueOnce(USER_A).mockResolvedValue(USER_B);
    render(<Tree />);
    await userEvent.click(await screen.findByRole('button', { name: 'open general' }));
    await screen.findByRole('textbox', BOX);

    await userEvent.click(screen.getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":"user-b"'));

    await userEvent.click(screen.getByRole('button', { name: 'open general' }));
    await userEvent.type(await screen.findByRole('textbox', BOX), 'What is it?{Enter}');
    await waitFor(() => expect(screen.getByText(RESPONSE.answer)).toBeInTheDocument());

    await waitFor(() => expect(window.sessionStorage.getItem(STORED_B_GENERAL) ?? '').toContain(RESPONSE.answer));
  });

  it("opens B's panel with an empty composer", async () => {
    mockGetCurrentUser.mockResolvedValueOnce(USER_A).mockResolvedValue(USER_B);
    render(<Tree />);
    await openWithDraft();

    await userEvent.click(screen.getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":"user-b"'));
    await userEvent.click(screen.getByRole('button', { name: 'open general' }));

    expect(await screen.findByRole('textbox', BOX)).toHaveValue('');
  });

  it("never renders B's panel open or on A's project", async () => {
    queryClient.setQueryData(queryKeys.project('project-of-a'), { id: 'project-of-a', name: 'Alpha' });
    mockGetCurrentUser.mockResolvedValueOnce(USER_A).mockResolvedValue(USER_B);
    render(<Tree />);
    await openWithDraft();
    expect(screen.getByText('Project “Alpha”')).toBeInTheDocument();
    panelRenders.length = 0;

    await userEvent.click(screen.getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":"user-b"'));
    await userEvent.click(screen.getByRole('button', { name: 'open general' }));
    await screen.findByRole('textbox', BOX);

    // B's panel is first rendered closed and without a project, and the project's name never shows again.
    const forB = panelRenders.filter((render) => render.userId === 'user-b');
    expect(forB[0]).toEqual({ userId: 'user-b', open: false, projectId: null });
    expect(forB.every((render) => render.projectId === null)).toBe(true);
    expect(screen.queryByText('Project “Alpha”')).not.toBeInTheDocument();
  });

  it('keeps what B stored between A signing out and B signing in', async () => {
    mockGetCurrentUser.mockResolvedValueOnce(USER_A).mockResolvedValue(USER_B);
    render(<Tree />);
    await openWithDraft();

    await userEvent.click(screen.getByRole('button', { name: 'sign out' }));
    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":null'));
    // The sign-out cleared everything; this is what B writes to the tab before signing in.
    window.sessionStorage.setItem(STORED_B_GENERAL, JSON.stringify([]));

    await userEvent.click(screen.getByRole('button', { name: 'sign in' }));
    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":"user-b"'));

    expect(window.sessionStorage.getItem(STORED_B_GENERAL)).not.toBeNull();
  });
});
