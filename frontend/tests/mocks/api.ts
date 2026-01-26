import { vi } from 'vitest';

/**
 * Creates a mock API client with all methods stubbed.
 * Override specific methods as needed in tests.
 */
export function createMockApi(overrides: Record<string, unknown> = {}) {
  return {
    getToken: vi.fn().mockReturnValue(null),
    setToken: vi.fn(),

    // Auth
    register: vi.fn().mockResolvedValue({ id: '1', email: 'test@example.com' }),
    login: vi.fn().mockResolvedValue({ access_token: 'mock-token', token_type: 'bearer' }),
    logout: vi.fn(),

    // Users
    getCurrentUser: vi.fn().mockResolvedValue(null),
    updateCurrentUser: vi.fn().mockResolvedValue({}),
    changePassword: vi.fn().mockResolvedValue(undefined),
    deleteAccount: vi.fn().mockResolvedValue(undefined),
    uploadPhoto: vi.fn().mockResolvedValue({}),
    deletePhoto: vi.fn().mockResolvedValue(undefined),

    // Projects
    getProjects: vi.fn().mockResolvedValue([]),
    getProject: vi.fn().mockResolvedValue(null),
    createProject: vi.fn().mockResolvedValue({}),
    updateProject: vi.fn().mockResolvedValue({}),
    deleteProject: vi.fn().mockResolvedValue(undefined),

    // Invitations
    inviteExpert: vi.fn().mockResolvedValue({}),
    getInvitations: vi.fn().mockResolvedValue([]),
    acceptInvitation: vi.fn().mockResolvedValue({}),
    declineInvitation: vi.fn().mockResolvedValue(undefined),

    // Members
    getMembers: vi.fn().mockResolvedValue([]),
    removeMember: vi.fn().mockResolvedValue(undefined),

    // Opinions
    getOpinions: vi.fn().mockResolvedValue([]),
    createOrUpdateOpinion: vi.fn().mockResolvedValue({}),
    deleteOpinion: vi.fn().mockResolvedValue(undefined),

    // Results
    getResult: vi.fn().mockResolvedValue(null),

    ...overrides,
  };
}

/**
 * Resets all mocks in the API object.
 */
export function resetApiMocks(mockApi: ReturnType<typeof createMockApi>) {
  Object.values(mockApi).forEach((mock) => {
    if (typeof mock === 'function' && 'mockReset' in mock) {
      (mock as ReturnType<typeof vi.fn>).mockReset();
    }
  });
}
