import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { DeleteAccountDialog } from '@/components/modals/DeleteAccountDialog';
import type { Member, ProjectWithRole } from '@/types/api';

const mockApi = {
  getProjects: vi.fn(),
  getMembers: vi.fn(),
  deleteAccount: vi.fn(),
};
vi.mock('@/lib/api', () => ({
  api: {
    getProjects: () => mockApi.getProjects(),
    getMembers: (id: string) => mockApi.getMembers(id),
    deleteAccount: (dispositions: unknown) => mockApi.deleteAccount(dispositions),
  },
}));

const CURRENT_USER_ID = 'owner-1';

function ownedProject(overrides: Partial<ProjectWithRole> = {}): ProjectWithRole {
  return {
    id: 'proj-1',
    name: 'Owned Project',
    description: null,
    scale_min: 0,
    scale_max: 100,
    scale_unit: '',
    admin_id: CURRENT_USER_ID,
    created_at: '2026-01-01T00:00:00Z',
    member_count: 2,
    is_example: false,
    role: 'admin',
    ...overrides,
  };
}

function member(overrides: Partial<Member> = {}): Member {
  return {
    user_id: 'member-1',
    email: 'jane@example.com',
    first_name: 'Jane',
    last_name: 'Roe',
    photo_url: null,
    role: 'expert',
    joined_at: '2026-01-02T00:00:00Z',
    ...overrides,
  };
}

function renderDialog(onConfirmed = vi.fn().mockResolvedValue(undefined)) {
  render(
    <DeleteAccountDialog
      open
      onOpenChange={vi.fn()}
      currentUserId={CURRENT_USER_ID}
      onConfirmed={onConfirmed}
    />
  );
  return { onConfirmed };
}

describe('DeleteAccountDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.getProjects.mockResolvedValue([]);
    mockApi.getMembers.mockResolvedValue([]);
    mockApi.deleteAccount.mockResolvedValue(undefined);
  });

  it('deletes with no dispositions when the user owns nothing', async () => {
    const user = userEvent.setup();
    const { onConfirmed } = renderDialog();

    const confirm = await screen.findByRole('button', { name: 'Delete My Account' });
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalledWith([]);
      expect(onConfirmed).toHaveBeenCalled();
    });
  });

  it('lists an owned project and deletes it by default', async () => {
    mockApi.getProjects.mockResolvedValue([ownedProject()]);
    mockApi.getMembers.mockResolvedValue([member()]);
    const user = userEvent.setup();
    renderDialog();

    expect(await screen.findByText('Owned Project')).toBeInTheDocument();

    const confirm = screen.getByRole('button', { name: 'Delete My Account' });
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalledWith([
        { project_id: 'proj-1', action: 'delete' },
      ]);
    });
  });

  it('shows an inline error and keeps the user when deletion fails', async () => {
    mockApi.deleteAccount.mockRejectedValueOnce(new Error('boom'));
    const user = userEvent.setup();
    const { onConfirmed } = renderDialog();

    const confirm = await screen.findByRole('button', { name: 'Delete My Account' });
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(onConfirmed).not.toHaveBeenCalled();
  });

  it('reports a load error and blocks deletion when projects fail to load', async () => {
    mockApi.getProjects.mockRejectedValueOnce(new Error('offline'));
    renderDialog();

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete My Account' })).toBeDisabled();
    expect(mockApi.deleteAccount).not.toHaveBeenCalled();
  });

  it('shows an accessible loading status while owned projects load', () => {
    mockApi.getProjects.mockReturnValue(new Promise(() => {}));
    renderDialog();

    // Exact match, not a substring regex: pins the resolved a11y.loading
    // translation so a broken i18n key (e.g. "aria.loading") fails loudly
    // instead of accidentally matching on its own literal text.
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
  });
});
