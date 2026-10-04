import { User } from '@/types/api';

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
