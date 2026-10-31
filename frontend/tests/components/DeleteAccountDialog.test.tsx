import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { DeleteAccountDialog } from '@/components/modals/DeleteAccountDialog';
import { HttpError } from '@/lib/errors';
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
    deleteAccount: (password: string, dispositions: unknown) =>
      mockApi.deleteAccount(password, dispositions),
  },
}));

const CURRENT_USER_ID = 'owner-1';
const PASSWORD = 'my-password';

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

/** Types the password once the dialog has loaded, then returns the confirm button. */
async function fillPassword(user: ReturnType<typeof userEvent.setup>, password = PASSWORD) {
  await user.type(await screen.findByLabelText('Current Password'), password);
  return screen.getByRole('button', { name: 'Delete My Account' });
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

    const confirm = await fillPassword(user);
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalledWith(PASSWORD, []);
      expect(onConfirmed).toHaveBeenCalled();
    });
  });

  it('lists an owned project and deletes it by default', async () => {
    mockApi.getProjects.mockResolvedValue([ownedProject()]);
    mockApi.getMembers.mockResolvedValue([member()]);
    const user = userEvent.setup();
    renderDialog();

    expect(await screen.findByText('Owned Project')).toBeInTheDocument();

    const confirm = await fillPassword(user);
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalledWith(PASSWORD, [
        { project_id: 'proj-1', action: 'delete' },
      ]);
    });
  });

  it('shows an inline error and keeps the user when deletion fails', async () => {
    mockApi.deleteAccount.mockRejectedValueOnce(new Error('boom'));
    const user = userEvent.setup();
    const { onConfirmed } = renderDialog();

    const confirm = await fillPassword(user);
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(onConfirmed).not.toHaveBeenCalled();
  });

  it('offers the members of a regular project as new admins', async () => {
    mockApi.getProjects.mockResolvedValue([ownedProject()]);
    mockApi.getMembers.mockResolvedValue([member()]);
    const user = userEvent.setup();
    renderDialog();

    await user.click(await screen.findByRole('combobox'));

    expect(await screen.findByRole('option', { name: 'Delete this project' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Transfer to Jane Roe' })).toBeInTheDocument();
  });

  it('offers only deletion for the example project, whose other members are demo experts', async () => {
    mockApi.getProjects.mockResolvedValue([ownedProject({ is_example: true })]);
    mockApi.getMembers.mockResolvedValue([
      member({ user_id: 'demo-1', first_name: 'Demo', last_name: 'Expert' }),
    ]);
    const user = userEvent.setup();
    renderDialog();

    await user.click(await screen.findByRole('combobox'));

    expect(await screen.findByRole('option', { name: 'Delete this project' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Transfer to/ })).not.toBeInTheDocument();
    expect(mockApi.getMembers).not.toHaveBeenCalled();
  });

  it('asks for the members of the regular project only and deletes the example project', async () => {
    mockApi.getProjects.mockResolvedValue([
      ownedProject({ id: 'example-1', name: 'Example Project', is_example: true }),
      ownedProject({ id: 'proj-2', name: 'Regular Project' }),
    ]);
    mockApi.getMembers.mockResolvedValue([member()]);
    const user = userEvent.setup();
    renderDialog();

    expect(await screen.findByText('Regular Project')).toBeInTheDocument();
    expect(mockApi.getMembers).toHaveBeenCalledTimes(1);
    expect(mockApi.getMembers).toHaveBeenCalledWith('proj-2');

    const confirm = await fillPassword(user);
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalledWith(PASSWORD, [
        { project_id: 'example-1', action: 'delete' },
        { project_id: 'proj-2', action: 'delete' },
      ]);
    });
  });

  it.each([
    [
      new HttpError('English server detail', 422, 'invalid_project_disposition'),
      'One of the chosen new admins cannot take over the project. Choose another member or delete the project.',
    ],
    [
      new HttpError('English server detail', 409, 'account_has_owned_projects'),
      'Your projects changed while this dialog was open. Close it and try again.',
    ],
    [
      new HttpError('English server detail', 422, 'some_other_code'),
      'Account deletion failed. Please try again.',
    ],
  ])('shows the translated line for a refused deletion (%s)', async (error, message) => {
    mockApi.deleteAccount.mockRejectedValueOnce(error);
    const user = userEvent.setup();
    const { onConfirmed } = renderDialog();

    const confirm = await fillPassword(user);
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(onConfirmed).not.toHaveBeenCalled();
  });

  it('clears the message of a refused deletion when the dialog is reopened', async () => {
    mockApi.deleteAccount.mockRejectedValueOnce(
      new HttpError('English server detail', 409, 'account_has_owned_projects')
    );
    const user = userEvent.setup();
    const props = {
      onOpenChange: vi.fn(),
      currentUserId: CURRENT_USER_ID,
      onConfirmed: vi.fn().mockResolvedValue(undefined),
    };
    const { rerender } = render(<DeleteAccountDialog open {...props} />);

    const confirm = await fillPassword(user);
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your projects changed while this dialog was open. Close it and try again.'
    );

    rerender(<DeleteAccountDialog open={false} {...props} />);
    rerender(<DeleteAccountDialog open {...props} />);

    await waitFor(() => expect(mockApi.getProjects).toHaveBeenCalledTimes(2));
    expect(await screen.findByLabelText('Current Password')).toHaveValue('');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('keeps the confirm button disabled until a password is typed', async () => {
    const user = userEvent.setup();
    renderDialog();

    const field = await screen.findByLabelText('Current Password');
    const confirm = screen.getByRole('button', { name: 'Delete My Account' });
    expect(confirm).toBeDisabled();

    await user.type(field, 'x');
    expect(confirm).toBeEnabled();

    await user.clear(field);
    expect(confirm).toBeDisabled();
  });

  it('sends the typed password with the dispositions', async () => {
    mockApi.getProjects.mockResolvedValue([ownedProject()]);
    mockApi.getMembers.mockResolvedValue([member()]);
    const user = userEvent.setup();
    renderDialog();

    const confirm = await fillPassword(user, 'Secret Pass 1!');
    await user.click(confirm);

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalledWith('Secret Pass 1!', [
        { project_id: 'proj-1', action: 'delete' },
      ]);
    });
  });

  it('submits when Enter is pressed in the password field', async () => {
    const user = userEvent.setup();
    const { onConfirmed } = renderDialog();

    await user.type(await screen.findByLabelText('Current Password'), `${PASSWORD}{Enter}`);

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalledWith(PASSWORD, []);
      expect(onConfirmed).toHaveBeenCalled();
    });
  });

  it('does not submit on Enter while the password is empty', async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.type(await screen.findByLabelText('Current Password'), '{Enter}');

    expect(mockApi.deleteAccount).not.toHaveBeenCalled();
  });

  it('shows the wrong-password message and keeps the dialog and its input after a refusal', async () => {
    mockApi.deleteAccount.mockRejectedValueOnce(
      new HttpError('Current password is incorrect', 400, 'current_password_incorrect')
    );
    const user = userEvent.setup();
    const { onConfirmed } = renderDialog();

    const confirm = await fillPassword(user, 'wrong-one');
    await user.click(confirm);

    expect(await screen.findByRole('alert')).toHaveTextContent('Current password is incorrect.');
    expect(onConfirmed).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Current Password')).toHaveValue('wrong-one');
    expect(screen.getByRole('button', { name: 'Delete My Account' })).toBeEnabled();
  });

  it('starts every opening from the default choices, not from a stale transfer', async () => {
    mockApi.getProjects.mockResolvedValue([ownedProject()]);
    mockApi.getMembers.mockResolvedValue([member()]);
    mockApi.deleteAccount.mockRejectedValueOnce(
      new HttpError('English server detail', 422, 'invalid_project_disposition')
    );
    const user = userEvent.setup();
    const props = {
      onOpenChange: vi.fn(),
      currentUserId: CURRENT_USER_ID,
      onConfirmed: vi.fn().mockResolvedValue(undefined),
    };
    const { rerender } = render(<DeleteAccountDialog open {...props} />);

    // GIVEN a transfer to Jane that the API refuses
    await user.click(await screen.findByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Transfer to Jane Roe' }));
    await user.click(await fillPassword(user));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(mockApi.deleteAccount).toHaveBeenLastCalledWith(PASSWORD, [
      { project_id: 'proj-1', action: 'transfer', new_admin_id: 'member-1' },
    ]);

    // WHEN the dialog is closed and reopened after Jane has left the project
    mockApi.getMembers.mockResolvedValue([]);
    rerender(<DeleteAccountDialog open={false} {...props} />);
    rerender(<DeleteAccountDialog open {...props} />);

    // THEN the choice is back to the default and the next submit deletes the project
    await waitFor(() => expect(mockApi.getProjects).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('combobox')).toHaveTextContent('Delete this project');
    await user.click(await fillPassword(user));

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenLastCalledWith(PASSWORD, [
        { project_id: 'proj-1', action: 'delete' },
      ]);
    });
  });

  it('reports a load error and blocks deletion when projects fail to load', async () => {
    mockApi.getProjects.mockRejectedValueOnce(new Error('offline'));
    renderDialog();

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete My Account' })).toBeDisabled();
    expect(screen.queryByLabelText('Current Password')).not.toBeInTheDocument();
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
