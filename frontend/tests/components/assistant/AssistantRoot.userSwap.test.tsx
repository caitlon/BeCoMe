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

const USER_A = { id: 'user-a', email: 'a@example.com', first_name: 'A' };
const USER_B = { id: 'user-b', email: 'b@example.com', first_name: 'B' };

// What Profile (photo, name, password) and ServiceUnavailable's retry do after a write:
// re-read the session cookie. Another tab that signed A out and B in has swapped it.
function Harness() {
  const { refreshUser, user } = useAuth();
  const { openAssistant, isOpen, projectId } = useAssistantUI();
  return (
    <>
      <button onClick={() => openAssistant('project-of-a')}>open</button>
      <button onClick={() => void refreshUser()}>refresh</button>
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

const STORED_A = `${STORAGE_PREFIX}:user-a:project-of-a`;

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
});
