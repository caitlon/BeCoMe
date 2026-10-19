import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { createUser } from '@tests/factories/user';
import { HttpError } from '@/lib/errors';
import type { User } from '@/types/api';
import { AssistantPrivacyCard } from '@/components/assistant/AssistantPrivacyCard';

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

// The card must hand the PUT response to setCurrentUser and never re-fetch with
// refreshUser, which would flip the auth status to "loading" and remount the page.
const auth = vi.hoisted(() => ({
  user: null as unknown as User | null,
  setCurrentUser: vi.fn(),
  refreshUser: vi.fn(),
}));

vi.mock('@/contexts/AuthContext', async () => {
  const { useState } = await import('react');
  return {
    useAuth: () => {
      const [user, setUser] = useState(auth.user);
      return {
        user,
        isLoading: false,
        isAuthenticated: true,
        refreshUser: auth.refreshUser,
        setCurrentUser: (next: User) => {
          auth.setCurrentUser(next);
          setUser(next);
        },
        logout: vi.fn(),
      };
    },
  };
});

function renderCard(user: User | null) {
  auth.user = user;
  return render(<AssistantPrivacyCard />);
}

describe('AssistantPrivacyCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the card with the control named by its label and described by the explanation', () => {
    renderCard(createUser());

    expect(screen.getByText('Assistant Privacy')).toBeInTheDocument();
    const checkbox = screen.getByRole('checkbox', { name: LABEL });
    expect(checkbox).not.toBeChecked();
    expect(checkbox).toHaveAccessibleDescription(/does not show your opinions/);
  });

  it('shows the control checked for a user who already objects', () => {
    renderCard(createUser({ assistant_objection: true }));

    expect(screen.getByRole('checkbox', { name: LABEL })).toBeChecked();
  });

  it('renders nothing without a signed-in user', () => {
    const { container } = renderCard(null);

    expect(container).toBeEmptyDOMElement();
  });

  it('saves the objection when it is switched on and keeps the page as it is', async () => {
    const user = userEvent.setup();
    const saved = createUser({ assistant_objection: true });
    mockUpdateCurrentUser.mockResolvedValueOnce(saved);
    renderCard(createUser());

    await user.click(screen.getByRole('checkbox', { name: LABEL }));

    await waitFor(() => {
      expect(mockUpdateCurrentUser).toHaveBeenCalledWith({ assistant_objection: true });
    });
    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: LABEL })).toBeChecked();
    });
    expect(auth.setCurrentUser).toHaveBeenCalledWith(saved);
    expect(auth.refreshUser).not.toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith({
      title: "Your opinions are now hidden from other members' assistant",
    });
  });

  it('saves the objection when it is switched off', async () => {
    const user = userEvent.setup();
    const saved = createUser({ assistant_objection: false });
    mockUpdateCurrentUser.mockResolvedValueOnce(saved);
    renderCard(createUser({ assistant_objection: true }));

    await user.click(screen.getByRole('checkbox', { name: LABEL }));

    await waitFor(() => {
      expect(mockUpdateCurrentUser).toHaveBeenCalledWith({ assistant_objection: false });
    });
    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: LABEL })).not.toBeChecked();
    });
    expect(auth.setCurrentUser).toHaveBeenCalledWith(saved);
    expect(auth.refreshUser).not.toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith({
      title: "Other members' assistant can show your opinions again",
    });
  });

  it('keeps the control as it was and shows the error when saving fails', async () => {
    const user = userEvent.setup();
    mockUpdateCurrentUser.mockRejectedValueOnce(new Error('boom'));
    renderCard(createUser());

    await user.click(screen.getByRole('checkbox', { name: LABEL }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', variant: 'destructive' })
      );
    });
    expect(screen.getByRole('checkbox', { name: LABEL })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: LABEL })).toBeEnabled();
    expect(auth.setCurrentUser).not.toHaveBeenCalled();
    expect(auth.refreshUser).not.toHaveBeenCalled();
  });

  it('shows the server message when the refusal carries one', async () => {
    const user = userEvent.setup();
    mockUpdateCurrentUser.mockRejectedValueOnce(new HttpError('Too slow', 500));
    renderCard(createUser());

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
    renderCard(createUser());

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
    renderCard(createUser());

    await user.click(screen.getByRole('checkbox', { name: LABEL }));

    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: LABEL })).toBeDisabled();
    });
    resolveSave(createUser({ assistant_objection: true }));
    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: LABEL })).toBeEnabled();
    });
  });
});
