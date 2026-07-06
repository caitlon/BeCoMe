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

describe('TeamTable - Member Row Interaction', () => {
  it('calls onMemberClick when a member row is clicked', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    await user.click(screen.getByRole('button', { name: /view profile of jane smith/i }));

    expect(onMemberClick).toHaveBeenCalledWith(members[0]);
  });

  it('calls onMemberClick when Enter is pressed on a member row', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    const row = screen.getByRole('button', { name: /view profile of jane smith/i });
    row.focus();
    await user.keyboard('{Enter}');

    expect(onMemberClick).toHaveBeenCalledWith(members[0]);
  });

  it('calls onMemberClick when Space is pressed on a member row', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    const row = screen.getByRole('button', { name: /view profile of jane smith/i });
    row.focus();
    await user.keyboard(' ');

    expect(onMemberClick).toHaveBeenCalledWith(members[0]);
  });

  it('does not call onMemberClick on an unrelated key press', async () => {
    const user = userEvent.setup();
    const onMemberClick = vi.fn();
    const members = [
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<TeamTable {...baseProps} members={members} pendingInvitations={[]} onMemberClick={onMemberClick} />);

    const row = screen.getByRole('button', { name: /view profile of jane smith/i });
    row.focus();
    await user.keyboard('{Tab}');

    expect(onMemberClick).not.toHaveBeenCalled();
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
