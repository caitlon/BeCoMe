import { User, Member } from '@/types/api';

let userCounter = 0;

/**
 * Creates a mock User object with default values.
 * Override specific fields as needed.
 */
export function createUser(overrides: Partial<User> = {}): User {
  userCounter++;
  return {
    id: `user-${userCounter}`,
    email: `user${userCounter}@example.com`,
    first_name: 'Test',
    last_name: 'User',
    photo_url: null,
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Creates a mock Member object with default values.
 */
export function createMember(overrides: Partial<Member> = {}): Member {
  userCounter++;
  return {
    user_id: `user-${userCounter}`,
    email: `member${userCounter}@example.com`,
    first_name: 'Member',
    last_name: 'User',
    role: 'expert',
    joined_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * Resets the counter for deterministic IDs in tests.
 */
export function resetUserCounter() {
  userCounter = 0;
}
