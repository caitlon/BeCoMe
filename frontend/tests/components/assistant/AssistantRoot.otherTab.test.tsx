import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import '@/i18n';
import AssistantRoot from '@/components/assistant/AssistantRoot';
import { STORAGE_PREFIX } from '@/components/assistant/history-storage';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { AssistantUIProvider, useAssistantUI } from '@/contexts/AssistantUIContext';
import { FakeBroadcastChannel } from '@tests/support/fake-broadcast-channel';

// The real AuthProvider, root and panel. Only the transport and the config are replaced, and
// the other tab is a bare channel on the same fake bus: nothing in this tab signs out locally.
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

const USER_A = { id: 'user-a', email: 'a@example.com', first_name: 'A' };
const USER_B = { id: 'user-b', email: 'b@example.com', first_name: 'B' };
const STORED_A = `${STORAGE_PREFIX}:user-a:project-of-a`;

function Harness() {
  const { user } = useAuth();
  const { openAssistant, isOpen, projectId } = useAssistantUI();
  return (
    <>
      <button onClick={() => openAssistant('project-of-a')}>open</button>
      <output data-testid="ui">{JSON.stringify({ user: user?.id ?? null, isOpen, projectId })}</output>
    </>
  );
}

function Tree() {
  return (
    <QueryClientProvider client={new QueryClient()}>
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

describe('AssistantRoot when another tab signs out or signs in', () => {
  let otherTab: FakeBroadcastChannel;

  beforeEach(() => {
    FakeBroadcastChannel.reset();
    vi.stubGlobal('BroadcastChannel', FakeBroadcastChannel);
    window.sessionStorage.clear();
    window.sessionStorage.setItem(STORED_A, JSON.stringify([]));
    mockGetCurrentUser.mockReset();
    otherTab = new FakeBroadcastChannel('become-auth');
  });

  afterEach(() => {
    otherTab.close();
    vi.unstubAllGlobals();
  });

  async function openWithDraft() {
    await userEvent.click(await screen.findByRole('button', { name: 'open' }));
    const composer = await screen.findByRole('textbox', { name: 'Ask a question…' });
    await userEvent.type(composer, 'a private draft of A');
    expect(screen.getByTestId('ui')).toHaveTextContent('"projectId":"project-of-a"');
  }

  it("takes A's panel, project and stored conversation away when the other tab signs out", async () => {
    mockGetCurrentUser.mockResolvedValue(USER_A);
    render(<Tree />);
    await openWithDraft();
    expect(window.sessionStorage.getItem(STORED_A)).not.toBeNull();

    act(() => otherTab.postMessage({ type: 'signed-out' }));

    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":null'));
    expect(screen.getByTestId('ui')).toHaveTextContent('"isOpen":false');
    expect(screen.getByTestId('ui')).toHaveTextContent('"projectId":null');
    expect(screen.queryByRole('textbox', { name: 'Ask a question…' })).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem(STORED_A)).toBeNull();
    // This tab only heard about it: it made no request and told nobody.
    expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
    expect(FakeBroadcastChannel.posted).toEqual([{ type: 'signed-out' }]);
  });

  it("does not hand A's history to B when the other tab signs B in", async () => {
    mockGetCurrentUser.mockResolvedValueOnce(USER_A).mockResolvedValue(USER_B);
    render(<Tree />);
    await openWithDraft();

    await act(async () => otherTab.postMessage({ type: 'signed-in' }));

    await waitFor(() => expect(screen.getByTestId('ui')).toHaveTextContent('"user":"user-b"'));
    expect(screen.getByTestId('ui')).toHaveTextContent('"isOpen":false');
    expect(screen.getByTestId('ui')).toHaveTextContent('"projectId":null');
    expect(screen.queryByDisplayValue('a private draft of A')).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem(STORED_A)).toBeNull();
  });
});
