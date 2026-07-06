import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { OtherOpinionsTable } from '@/components/project';
import { createOpinion, createMember } from '@tests/factories/project';

describe('OtherOpinionsTable - Empty State', () => {
  it('shows "no other opinions" when empty', () => {
    render(<OtherOpinionsTable opinions={[]} members={[]} currentUserId="user-1" />);

    expect(screen.getByText('No other opinions yet')).toBeInTheDocument();
  });
});

describe('OtherOpinionsTable - Sorting', () => {
  it('displays other expert opinions sorted by centroid descending', () => {
    // Bob has lower centroid than Jane, but is listed first in input array
    const opinions = [
      createOpinion({
        user_id: 'other-user-2',
        user_first_name: 'Bob',
        user_last_name: 'Brown',
        lower_bound: 10,
        peak: 20,
        upper_bound: 30,
        centroid: 20,
      }),
      createOpinion({
        user_id: 'other-user',
        user_first_name: 'Jane',
        user_last_name: 'Smith',
        lower_bound: 30,
        peak: 60,
        upper_bound: 90,
        centroid: 60,
      }),
    ];

    render(<OtherOpinionsTable opinions={opinions} members={[]} currentUserId="user-1" />);

    // Verify descending centroid order: Jane (60) before Bob (20)
    const janeEl = screen.getByText('Jane Smith');
    const bobEl = screen.getByText('Bob Brown');
    // Node.DOCUMENT_POSITION_FOLLOWING (4) means bob comes after jane
    expect(janeEl.compareDocumentPosition(bobEl) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe('OtherOpinionsTable - Pending Members', () => {
  it('shows awaiting response for members without opinions', () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
      createMember({ user_id: 'user-3', first_name: 'Anna', last_name: 'Lee', role: 'expert' }),
    ];
    const opinions = [
      createOpinion({ user_id: 'user-2', user_first_name: 'Jane', user_last_name: 'Smith' }),
    ];

    render(<OtherOpinionsTable opinions={opinions} members={members} currentUserId="user-1" />);

    // Anna has no opinion and is not the current user — should see "Awaiting response"
    expect(screen.getByText('Awaiting response')).toBeInTheDocument();
    // Verify Anna specifically appears as pending
    expect(screen.getByText('Anna Lee')).toBeInTheDocument();
  });

  it('does not show current user as pending member', () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    // No opinions at all — user-1 (current user) should NOT appear as pending
    render(<OtherOpinionsTable opinions={[]} members={members} currentUserId="user-1" />);

    // Only Jane should be pending — current user (John) must be excluded.
    expect(screen.getAllByText('Awaiting response')).toHaveLength(1);
    expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
  });

  it('shows table when only pending members exist (no opinions)', () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];

    render(<OtherOpinionsTable opinions={[]} members={members} currentUserId="user-1" />);

    // Table should render (not "no other opinions" empty state)
    expect(screen.getByText('Awaiting response')).toBeInTheDocument();
    expect(screen.queryByText('No other opinions yet')).not.toBeInTheDocument();
  });
});
