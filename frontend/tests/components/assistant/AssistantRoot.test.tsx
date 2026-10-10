import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import i18n from '@/i18n';
import AssistantRoot from '@/components/assistant/AssistantRoot';
import { STORAGE_PREFIX } from '@/components/assistant/useAssistantChat';
import { AssistantUIProvider, useAssistantUI } from '@/contexts/AssistantUIContext';

const mockSetAvailable = vi.fn();
const mockCloseAssistant = vi.fn();
let mockAuth: { isAuthenticated: boolean; user: { id: string } | null } = {
  isAuthenticated: true,
  user: { id: 'u1' },
};
let mockUI = { isOpen: false, projectId: null as string | null };
let signOutListener: (() => void) | undefined;
const mockUnsubscribe = vi.fn();

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
  registerSignOutListener: (listener: () => void) => {
    signOutListener = listener;
    return mockUnsubscribe;
  },
}));
let useRealUI = false;
vi.mock('@/contexts/AssistantUIContext', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/contexts/AssistantUIContext')>();
  return {
    ...actual,
    useAssistantUI: () =>
      useRealUI
        ? actual.useAssistantUI()
        : { ...mockUI, setAvailable: mockSetAvailable, closeAssistant: mockCloseAssistant },
  };
});

const mockUseAssistantConfig = vi.fn();
vi.mock('@/components/assistant/useAssistantConfig', () => ({
  useAssistantConfig: (enabled: boolean) => mockUseAssistantConfig(enabled),
}));
vi.mock('@/components/assistant/AssistantPanel', () => ({
  AssistantPanel: ({ open, projectId, userId, mode, onOpenChange }: {
    open: boolean; projectId: string | null; userId: string; mode: string; onOpenChange: (open: boolean) => void;
  }) => (
    <div data-testid="panel" data-open={String(open)} data-project={projectId ?? ''} data-user={userId} data-mode={mode}>
      <button onClick={() => onOpenChange(false)}>dismiss</button>
      <button onClick={() => onOpenChange(true)}>reopen</button>
    </div>
  ),
}));

const enabledConfig = { isSuccess: true, data: { enabled: true, model: 'x', mode: 'hybrid' } };

describe('AssistantRoot', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth = { isAuthenticated: true, user: { id: 'u1' } };
    mockUI = { isOpen: false, projectId: null };
    signOutListener = undefined;
    useRealUI = false;
    window.sessionStorage.clear();
  });

  it('renders nothing and reports unavailable while the config query is loading', async () => {
    mockUseAssistantConfig.mockReturnValue({ isSuccess: false, data: undefined });

    render(<AssistantRoot />);

    expect(screen.queryByTestId('panel')).not.toBeInTheDocument();
    await waitFor(() => expect(mockSetAvailable).toHaveBeenCalledWith(false));
  });

  it('renders nothing when the config query fails (404, feature off server-side)', async () => {
    mockUseAssistantConfig.mockReturnValue({ isSuccess: false, data: undefined, isError: true });

    render(<AssistantRoot />);

    expect(screen.queryByTestId('panel')).not.toBeInTheDocument();
    await waitFor(() => expect(mockSetAvailable).toHaveBeenCalledWith(false));
  });

  it('renders nothing when the backend answers enabled: false', async () => {
    mockUseAssistantConfig.mockReturnValue({ isSuccess: true, data: { enabled: false } });

    render(<AssistantRoot />);

    expect(screen.queryByTestId('panel')).not.toBeInTheDocument();
    await waitFor(() => expect(mockSetAvailable).toHaveBeenCalledWith(false));
  });

  it('asks for the config only for a signed-in user, and is unavailable for a guest', async () => {
    mockAuth = { isAuthenticated: false, user: null };
    mockUseAssistantConfig.mockReturnValue(enabledConfig);

    render(<AssistantRoot />);

    expect(mockUseAssistantConfig).toHaveBeenCalledWith(false);
    expect(screen.queryByTestId('panel')).not.toBeInTheDocument();
    await waitFor(() => expect(mockSetAvailable).toHaveBeenCalledWith(false));
  });

  it('marks the assistant available and passes the open state down once the config is enabled', async () => {
    mockUI = { isOpen: true, projectId: 'p1' };
    mockUseAssistantConfig.mockReturnValue(enabledConfig);

    render(<AssistantRoot />);

    await waitFor(() => expect(mockSetAvailable).toHaveBeenCalledWith(true));
    const panel = screen.getByTestId('panel');
    expect(panel).toHaveAttribute('data-open', 'true');
    expect(panel).toHaveAttribute('data-project', 'p1');
  });

  it('gives the panel the signed-in user and the mode of the backend', () => {
    mockUseAssistantConfig.mockReturnValue(enabledConfig);
    mockAuth = { isAuthenticated: true, user: { id: 'user-42' } };

    render(<AssistantRoot />);

    expect(screen.getByTestId('panel')).toHaveAttribute('data-user', 'user-42');
    expect(screen.getByTestId('panel')).toHaveAttribute('data-mode', 'hybrid');
  });

  it('renders no panel for a session that has no user yet', () => {
    mockUseAssistantConfig.mockReturnValue(enabledConfig);
    mockAuth = { isAuthenticated: true, user: null };

    render(<AssistantRoot />);

    expect(screen.queryByTestId('panel')).not.toBeInTheDocument();
  });

  it('closes the assistant when the panel asks to close, and ignores a request to open', async () => {
    mockUseAssistantConfig.mockReturnValue(enabledConfig);
    render(<AssistantRoot />);

    await act(async () => screen.getByText('reopen').click());
    expect(mockCloseAssistant).not.toHaveBeenCalled();

    await act(async () => screen.getByText('dismiss').click());
    expect(mockCloseAssistant).toHaveBeenCalledTimes(1);
  });

  it('closes the assistant on sign-out and stops listening on unmount', () => {
    mockUseAssistantConfig.mockReturnValue(enabledConfig);
    const { unmount } = render(<AssistantRoot />);

    signOutListener?.();
    expect(mockCloseAssistant).toHaveBeenCalledTimes(1);

    unmount();
    expect(mockUnsubscribe).toHaveBeenCalled();
  });

  it('forgets every stored conversation on sign-out and leaves other storage alone', () => {
    mockUseAssistantConfig.mockReturnValue(enabledConfig);
    window.sessionStorage.setItem(`${STORAGE_PREFIX}:u1:general`, '[]');
    window.sessionStorage.setItem('unrelated', 'kept');
    render(<AssistantRoot />);

    signOutListener?.();

    expect(window.sessionStorage.getItem(`${STORAGE_PREFIX}:u1:general`)).toBeNull();
    expect(window.sessionStorage.getItem('unrelated')).toBe('kept');
  });

  it('forgets the stored conversations before it closes the panel', () => {
    mockUseAssistantConfig.mockReturnValue(enabledConfig);
    window.sessionStorage.setItem(`${STORAGE_PREFIX}:u1:general`, '[]');
    let storedWhenClosed: string | null = 'not read';
    mockCloseAssistant.mockImplementation(() => {
      storedWhenClosed = window.sessionStorage.getItem(`${STORAGE_PREFIX}:u1:general`);
    });
    render(<AssistantRoot />);

    signOutListener?.();

    expect(storedWhenClosed).toBeNull();
  });

  it('registers the assistant i18n bundle for both locales', () => {
    mockUseAssistantConfig.mockReturnValue({ isSuccess: false, data: undefined });

    render(<AssistantRoot />);

    expect(i18n.hasResourceBundle('en', 'assistant')).toBe(true);
    expect(i18n.hasResourceBundle('cs', 'assistant')).toBe(true);
  });

  it('drops availability and closes the panel when the root unmounts', async () => {
    useRealUI = true;
    mockUseAssistantConfig.mockReturnValue(enabledConfig);
    function Reader() {
      const { isAvailable, isOpen, openAssistant } = useAssistantUI();
      return (
        <>
          <span data-testid="state">{`${isAvailable}/${isOpen}`}</span>
          <button onClick={() => openAssistant()}>open</button>
        </>
      );
    }
    function Harness({ showRoot }: { showRoot: boolean }) {
      return (
        <AssistantUIProvider>
          <Reader />
          {showRoot && <AssistantRoot />}
        </AssistantUIProvider>
      );
    }

    const { rerender } = render(<Harness showRoot />);
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('true/false'));
    await act(async () => screen.getByText('open').click());
    expect(screen.getByTestId('state')).toHaveTextContent('true/true');

    rerender(<Harness showRoot={false} />);

    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('false/false'));
  });
});
