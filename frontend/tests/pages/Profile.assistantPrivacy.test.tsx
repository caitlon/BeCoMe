import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import { createUser } from '@tests/factories/user';
import { HttpError } from '@/lib/errors';
import type { User } from '@/types/api';

const LABEL = "Hide my opinions from other members' assistant";

const mockUpdateCurrentUser = vi.fn();
vi.mock('@/lib/api', async (importActual) => {
  const actual = await importActual<typeof import('@/lib/api')>();
  return {
    ...actual,
    api: { updateCurrentUser: (data: unknown) => mockUpdateCurrentUser(data) },
  };
});

const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// The "server": what the next refreshUser() hands back to the page.
const server = vi.hoisted(() => ({ user: null as unknown as User }));

vi.mock('@/contexts/AuthContext', async () => {
  const { useState } = await import('react');
  return {
    useAuth: () => {
      const [user, setUser] = useState(server.user);
      return {
        user,
        isLoading: false,
        isAuthenticated: true,
        refreshUser: async () => setUser(server.user),
        logout: vi.fn(),
      };
    },
  };
});

vi.mock('framer-motion', () => framerMotionMock);

async function renderProfile(user: User) {
  server.user = user;
  const { default: Profile } = await import('@/pages/Profile');
  return render(<Profile />);
}

describe('Profile - assistant privacy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('in a build without the assistant', () => {
    it('does not show the card', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      await renderProfile(createUser());

      expect(screen.getByText('Edit Profile')).toBeInTheDocument();
      expect(screen.queryByText('Assistant Privacy')).not.toBeInTheDocument();
      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    });
  });

  describe('in a build with the assistant', () => {
    beforeEach(() => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
    });

    it('shows the card with the control named by its label and described by the explanation', async () => {
      await renderProfile(createUser());

      expect(screen.getByText('Assistant Privacy')).toBeInTheDocument();
      const checkbox = screen.getByRole('checkbox', { name: LABEL });
      expect(checkbox).not.toBeChecked();
      expect(checkbox).toHaveAccessibleDescription(/does not show your opinions/);
    });

    it('shows the control checked for a user who already objects', async () => {
      await renderProfile(createUser({ assistant_objection: true }));

      expect(screen.getByRole('checkbox', { name: LABEL })).toBeChecked();
    });

    it('saves the objection when it is switched on', async () => {
      const user = userEvent.setup();
      mockUpdateCurrentUser.mockImplementationOnce(async () => {
        server.user = { ...server.user, assistant_objection: true };
        return server.user;
      });
      await renderProfile(createUser());

      await user.click(screen.getByRole('checkbox', { name: LABEL }));

      await waitFor(() => {
        expect(mockUpdateCurrentUser).toHaveBeenCalledWith({ assistant_objection: true });
      });
      await waitFor(() => {
        expect(screen.getByRole('checkbox', { name: LABEL })).toBeChecked();
      });
      expect(mockToast).toHaveBeenCalledWith({
        title: "Your opinions are now hidden from other members' assistant",
      });
    });

    it('saves the objection when it is switched off', async () => {
      const user = userEvent.setup();
      mockUpdateCurrentUser.mockImplementationOnce(async () => {
        server.user = { ...server.user, assistant_objection: false };
        return server.user;
      });
      await renderProfile(createUser({ assistant_objection: true }));

      await user.click(screen.getByRole('checkbox', { name: LABEL }));

      await waitFor(() => {
        expect(mockUpdateCurrentUser).toHaveBeenCalledWith({ assistant_objection: false });
      });
      await waitFor(() => {
        expect(screen.getByRole('checkbox', { name: LABEL })).not.toBeChecked();
      });
      expect(mockToast).toHaveBeenCalledWith({
        title: "Other members' assistant can show your opinions again",
      });
    });

    it('keeps the control as it was and shows the error when saving fails', async () => {
      const user = userEvent.setup();
      mockUpdateCurrentUser.mockRejectedValueOnce(new Error('boom'));
      await renderProfile(createUser());

      await user.click(screen.getByRole('checkbox', { name: LABEL }));

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({ title: 'Error', variant: 'destructive' })
        );
      });
      expect(screen.getByRole('checkbox', { name: LABEL })).not.toBeChecked();
      expect(screen.getByRole('checkbox', { name: LABEL })).toBeEnabled();
    });

    it('shows the server message when the refusal carries one', async () => {
      const user = userEvent.setup();
      mockUpdateCurrentUser.mockRejectedValueOnce(new HttpError('Too slow', 500));
      await renderProfile(createUser());

      await user.click(screen.getByRole('checkbox', { name: LABEL }));

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({ title: 'Error', description: 'Too slow' })
        );
      });
    });

    it('falls back to the card message for an unrecognised error', async () => {
      const user = userEvent.setup();
      mockUpdateCurrentUser.mockRejectedValueOnce('unknown');
      await renderProfile(createUser());

      await user.click(screen.getByRole('checkbox', { name: LABEL }));

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            description: 'Could not save the assistant setting',
          })
        );
      });
    });

    it('disables the control while the request is pending', async () => {
      const user = userEvent.setup();
      let resolveSave: (value: User) => void = () => {};
      mockUpdateCurrentUser.mockImplementationOnce(
        () => new Promise<User>((resolve) => { resolveSave = resolve; })
      );
      await renderProfile(createUser());

      await user.click(screen.getByRole('checkbox', { name: LABEL }));

      await waitFor(() => {
        expect(screen.getByRole('checkbox', { name: LABEL })).toBeDisabled();
      });
      server.user = { ...server.user, assistant_objection: true };
      resolveSave(server.user);
      await waitFor(() => {
        expect(screen.getByRole('checkbox', { name: LABEL })).toBeEnabled();
      });
    });
  });
});
