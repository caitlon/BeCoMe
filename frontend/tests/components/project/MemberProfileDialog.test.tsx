import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { MemberProfileDialog } from '@/components/project';
import { createMember, createOpinion } from '@tests/factories/project';
import type { Member } from '@/types/api';

describe('MemberProfileDialog - No Member', () => {
  it('renders nothing when member is null', () => {
    render(<MemberProfileDialog member={null} opinion={null} onOpenChange={vi.fn()} />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('MemberProfileDialog - Basic Rendering', () => {
  it('renders the member name as the dialog heading', () => {
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'expert' });

    render(<MemberProfileDialog member={member} opinion={null} onOpenChange={vi.fn()} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Jane Smith' })).toBeInTheDocument();
  });

  it('displays role badge in profile dialog', () => {
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'expert' });

    render(<MemberProfileDialog member={member} opinion={null} onOpenChange={vi.fn()} />);

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Expert')).toBeInTheDocument();
  });

  it('shows admin badge variant in profile dialog for admin member', () => {
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'admin' });

    render(<MemberProfileDialog member={member} opinion={null} onOpenChange={vi.fn()} />);

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Admin')).toBeInTheDocument();
  });

  it('handles member with null last_name', () => {
    const member = createMember({ first_name: 'Madonna', last_name: null, role: 'expert' });

    render(<MemberProfileDialog member={member} opinion={null} onOpenChange={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Madonna' })).toBeInTheDocument();
  });

  it('renders without crashing for a member with a photo_url', () => {
    const member = createMember({
      first_name: 'Jane',
      last_name: 'Smith',
      role: 'expert',
      photo_url: 'https://example.com/photo.jpg',
    });

    render(<MemberProfileDialog member={member} opinion={null} onOpenChange={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Jane Smith' })).toBeInTheDocument();
  });
});

describe('MemberProfileDialog - Opinion Content', () => {
  it('displays opinion values and position in profile dialog', () => {
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'expert' });
    const opinion = createOpinion({
      user_id: member.user_id,
      position: 'Head of Research',
      lower_bound: 10,
      peak: 20,
      upper_bound: 30,
      centroid: 20,
    });

    render(<MemberProfileDialog member={member} opinion={opinion} onOpenChange={vi.fn()} />);

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Head of Research')).toBeInTheDocument();
    // Opinion values are in an sr-only summary (the visible grid is aria-hidden)
    expect(within(dialog).getByText(/opinion values.*lower.*10\.00.*peak.*20\.00.*upper.*30\.00.*centroid.*20\.00/i)).toBeInTheDocument();
  });

  it('provides sr-only opinion summary for screen readers', () => {
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'expert' });
    const opinion = createOpinion({
      user_id: member.user_id,
      lower_bound: 10,
      peak: 20,
      upper_bound: 30,
      centroid: 20,
    });

    render(<MemberProfileDialog member={member} opinion={opinion} onOpenChange={vi.fn()} />);

    expect(screen.getByText(/opinion values.*lower.*10\.00.*peak.*20\.00.*upper.*30\.00.*centroid.*20\.00/i)).toBeInTheDocument();
  });

  it('shows no opinion message when member has no opinion', () => {
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'expert' });

    render(<MemberProfileDialog member={member} opinion={null} onOpenChange={vi.fn()} />);

    expect(screen.getByText('No opinion submitted yet')).toBeInTheDocument();
  });
});

describe('MemberProfileDialog - Closing', () => {
  function Harness({ initialMember }: { initialMember: Member | null }) {
    const [member, setMember] = useState(initialMember);
    return (
      <MemberProfileDialog
        member={member}
        opinion={null}
        onOpenChange={(open) => !open && setMember(null)}
      />
    );
  }

  it('closes the dialog when dismissed', async () => {
    const user = userEvent.setup();
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'expert' });

    render(<Harness initialMember={member} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('calls onOpenChange(false) when dismissed', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const member = createMember({ first_name: 'Jane', last_name: 'Smith', role: 'expert' });

    render(<MemberProfileDialog member={member} opinion={null} onOpenChange={onOpenChange} />);

    await user.keyboard('{Escape}');

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
