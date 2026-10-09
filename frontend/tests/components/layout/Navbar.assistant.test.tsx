import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';

const mockOpenAssistant = vi.fn();

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', email: 'a@b.com', first_name: 'A', last_name: 'B', photo_url: null, created_at: '' },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

// Static, not per-test: only the env var varies below, and both cases want
// the backend to look available once (if ever) the trigger chunk loads.
vi.mock('@/contexts/AssistantUIContext', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/contexts/AssistantUIContext')>()),
  useAssistantUI: () => ({
    isAvailable: true, isOpen: false, projectId: null,
    setAvailable: vi.fn(), setProjectScope: vi.fn(), openAssistant: mockOpenAssistant, closeAssistant: vi.fn(),
  }),
}));

describe('Navbar assistant trigger (real slot + lazy chunk)', () => {
  beforeEach(() => {
    vi.resetModules();
    mockOpenAssistant.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders no trigger in a build without the flag', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', '');
    const { Navbar: FreshNavbar } = await import('@/components/layout/Navbar');

    render(<FreshNavbar />);

    expect(screen.queryByRole('button', { name: 'Assistant' })).not.toBeInTheDocument();
  });

  it('renders the trigger in both button groups once the lazy chunk resolves in a build with the flag', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
    const { Navbar: FreshNavbar } = await import('@/components/layout/Navbar');
    const user = userEvent.setup();

    render(<FreshNavbar />);
    const buttons = await screen.findAllByRole('button', { name: 'Assistant' });
    await user.click(buttons[0]);

    expect(buttons).toHaveLength(2);
    expect(mockOpenAssistant).toHaveBeenCalledWith(undefined);
  });
});
