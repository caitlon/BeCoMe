import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import { createUser } from '@tests/factories/user';

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return { ...actual, useNavigate: () => vi.fn() };
});

vi.mock('@/lib/api', () => ({
  api: {
    updateCurrentUser: vi.fn(),
    changePassword: vi.fn(),
    deleteAccount: vi.fn(),
    uploadPhoto: vi.fn(),
    deletePhoto: vi.fn(),
    exportData: vi.fn(),
  },
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const mockUser = createUser({ first_name: 'John', last_name: 'Doe' });
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    refreshUser: vi.fn(),
    setCurrentUser: vi.fn(),
    logout: vi.fn(),
  }),
}));

describe('Profile assistant privacy card', () => {
  beforeEach(() => {
    // The slot computes its build flag once at module scope, so the page and
    // the helpers that share its i18n instance are re-imported per test.
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('shows the privacy card on the profile page in a build with the assistant', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
    const { default: Profile } = await import('@/pages/Profile');
    const { render } = await import('@tests/utils');

    render(<Profile />);

    expect(
      await screen.findByRole('checkbox', {
        name: "Hide my opinions from other members' assistant",
      })
    ).toBeInTheDocument();
  });
});
