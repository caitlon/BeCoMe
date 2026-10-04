import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { TeamTable } from '@/components/project';
import { createMember, createProjectInvitation } from '@tests/factories/project';

const baseProps = {
  isAdmin: true,
  currentUserId: 'user-1',
  onRemove: vi.fn(),
  onTransfer: vi.fn(),
  onMemberClick: vi.fn(),
};

describe('TeamTable - Rendering', () => {
  it('displays member avatar initials in team table', () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} />);

    expect(screen.getByText('JD')).toBeInTheDocument();
  });

  it('renders a member with a photo_url without crashing, falling back to initials', () => {
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert', photo_url: 'https://example.com/photo.jpg' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} />);

    // The AvatarImage only swaps in once the image finishes loading (never happens
    // in the test environment), so the initials fallback is what actually renders.
    expect(screen.getByText('JS')).toBeInTheDocument();
  });

  it('renders the joined date through the shared formatDate helper', () => {
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', joined_at: '2024-03-15T12:00:00Z' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} />);

    // Spelled-out month, not a bare numeric date (AUD-031): unambiguous
    // regardless of DD/MM vs MM/DD locale conventions.
    expect(screen.getByText('Mar 15, 2024')).toBeInTheDocument();
  });
});

describe('TeamTable - Pending Invitations', () => {
  it('displays pending invitations in team table', () => {
    const invitations = [
      createProjectInvitation({
        invitee_first_name: 'Sophie',
        invitee_last_name: 'Wagner',
        invitee_email: 'sophie@example.com',
      }),
    ];

    render(<TeamTable {...baseProps} members={[]} pendingInvitations={invitations} />);

    expect(screen.getByText('Invited')).toBeInTheDocument();
  });

  it('shows invitee name and email in team table', () => {
    const invitations = [
      createProjectInvitation({
        invitee_first_name: 'Michael',
        invitee_last_name: 'Brown',
        invitee_email: 'michael@example.com',
      }),
    ];

    render(<TeamTable {...baseProps} members={[]} pendingInvitations={invitations} />);

    expect(screen.getByText('Michael Brown')).toBeInTheDocument();
    expect(screen.getByText('michael@example.com')).toBeInTheDocument();
  });

  it('displays invitation when invitee has null last name', () => {
    const invitations = [
      createProjectInvitation({
        invitee_first_name: 'Cher',
        invitee_last_name: null,
        invitee_email: 'cher@example.com',
      }),
    ];

    render(<TeamTable {...baseProps} members={[]} pendingInvitations={invitations} />);

    expect(screen.getByText('Cher')).toBeInTheDocument();
  });
});

describe('TeamTable - Row Semantics', () => {
  const members = [
    createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
  ];

  it('keeps rows as plain rows, not buttons', () => {
    const { container } = render(
      <TeamTable
        {...baseProps}
        members={members}
        pendingInvitations={[createProjectInvitation()]}
      />
    );

    // header row + member row + invitation row, all still exposed as rows
    expect(screen.getAllByRole('row')).toHaveLength(3);
    for (const row of container.querySelectorAll('tr')) {
      expect(row).not.toHaveAttribute('role');
      expect(row).not.toHaveAttribute('tabindex');
      expect(row).not.toHaveAttribute('aria-label');
    }
  });

  it('gives the actions column header an accessible name', () => {
    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} />);

    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument();
  });

  it('renders no actions column header for a non-admin', () => {
    render(<TeamTable {...baseProps} isAdmin={false} members={members} pendingInvitations={[]} />);

    expect(screen.queryByRole('columnheader', { name: 'Actions' })).not.toBeInTheDocument();
  });

  it('marks the selected member control with aria-current', () => {
    render(
      <TeamTable
        {...baseProps}
        members={members}
        pendingInvitations={[]}
        selectedMemberId="user-2"
      />
    );

    expect(screen.getByRole('button', { name: /view profile of jane smith/i })).toHaveAttribute(
      'aria-current',
      'true'
    );
  });
});

describe('TeamTable - Member Row Interaction', () => {
  it('calls onMemberClick once when the member control is clicked', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    await user.click(screen.getByRole('button', { name: /view profile of jane smith/i }));

    expect(onMemberClick).toHaveBeenCalledTimes(1);
    expect(onMemberClick).toHaveBeenCalledWith(members[0]);
  });

  it('keeps the row click as a mouse convenience', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({
        user_id: 'user-2',
        first_name: 'Jane',
        last_name: 'Smith',
        email: 'jane.smith@example.com',
        role: 'expert',
      }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    await user.click(screen.getByText('jane.smith@example.com'));

    expect(onMemberClick).toHaveBeenCalledTimes(1);
    expect(onMemberClick).toHaveBeenCalledWith(members[0]);
  });

  it('reaches the member control with Tab and opens it with Enter', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    await user.tab();
    expect(screen.getByRole('button', { name: /view profile of jane smith/i })).toHaveFocus();

    await user.keyboard('{Enter}');

    expect(onMemberClick).toHaveBeenCalledTimes(1);
    expect(onMemberClick).toHaveBeenCalledWith(members[0]);
  });

  it('opens the member control with Space', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    await user.tab();
    await user.keyboard(' ');

    expect(onMemberClick).toHaveBeenCalledTimes(1);
    expect(onMemberClick).toHaveBeenCalledWith(members[0]);
  });

  it('puts the member control first in the tab order, before the row actions', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} />);

    await user.tab();
    expect(screen.getByRole('button', { name: /view profile of jane smith/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: /make jane smith the owner/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: /remove jane smith from team/i })).toHaveFocus();
  });

  it('does not call onMemberClick when the remove button is clicked, and calls onRemove instead', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const onRemove = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(
      <TeamTable
        {...baseProps}
        members={members}
        pendingInvitations={[]}
        onMemberClick={onMemberClick}
        onRemove={onRemove}
      />
    );

    await user.click(screen.getByRole('button', { name: /remove jane smith from team/i }));

    expect(onRemove).toHaveBeenCalledWith('user-2');
    expect(onMemberClick).not.toHaveBeenCalled();
  });
});
