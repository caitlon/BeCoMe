import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Store original location
const originalLocation = window.location;

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Import api after mocks are set up
// We need to re-import to get a fresh instance each test
let api: typeof import('@/lib/api').api;

describe('ApiClient', () => {
  beforeEach(async () => {
    vi.resetModules();
    localStorageMock.clear();
    mockFetch.mockReset();

    // Mock window.location
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    });

    // Re-import api to get fresh instance
    const module = await import('@/lib/api');
    api = module.api;
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
    });
  });

  describe('Token Management', () => {
    it('reads token from localStorage on initialization', async () => {
      localStorageMock.setItem('become_token', 'stored-token');
      vi.resetModules();
      const module = await import('@/lib/api');
      expect(module.api.getToken()).toBe('stored-token');
    });

    it('setToken stores token in localStorage', () => {
      api.setToken('new-token');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('become_token', 'new-token');
      expect(api.getToken()).toBe('new-token');
    });

    it('setToken(null) removes token from localStorage', () => {
      api.setToken('token');
      api.setToken(null);
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('become_token');
      expect(api.getToken()).toBeNull();
    });

    it('getToken returns current token', () => {
      expect(api.getToken()).toBeNull();
      api.setToken('my-token');
      expect(api.getToken()).toBe('my-token');
    });
  });

  describe('Request Handling', () => {
    it('adds Authorization header when token exists', async () => {
      api.setToken('bearer-token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: '1' }),
      });

      await api.getCurrentUser();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer bearer-token',
          }),
        })
      );
    });

    it('omits Authorization header when no token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      });

      await api.getProjects();

      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers.Authorization).toBeUndefined();
    });

    it('handles successful JSON response', async () => {
      const userData = { id: '1', email: 'test@example.com' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(userData),
      });

      api.setToken('token');
      const result = await api.getCurrentUser();
      expect(result).toEqual(userData);
    });

    it('handles 204 No Content response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      api.setToken('token');
      const result = await api.deleteProject('1');
      expect(result).toBeUndefined();
    });

    it('parses error response with string detail', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Bad request message' }),
      });

      api.setToken('token');
      await expect(api.getProjects()).rejects.toThrow('Bad request message');
    });

    it('parses error response with validation array detail', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () =>
          Promise.resolve({
            detail: [{ loc: ['body', 'email'], msg: 'Invalid email format', type: 'value_error' }],
          }),
      });

      api.setToken('token');
      await expect(api.getProjects()).rejects.toThrow('Invalid email format');
    });

    it('redirects to /login on 401 and clears token', async () => {
      api.setToken('expired-token');
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      });

      await expect(api.getProjects()).rejects.toThrow();
      expect(api.getToken()).toBeNull();
      expect(window.location.href).toBe('/login');
    });

    it('handles JSON parse error gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      api.setToken('token');
      await expect(api.getProjects()).rejects.toThrow('An unexpected error occurred');
    });

    it('throws HttpError with correct status for 400', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Bad request' }),
      });

      api.setToken('token');
      try {
        await api.getProjects();
        expect.fail('Expected HttpError to be thrown');
      } catch (e: unknown) {
        const err = e as { name: string; status: number; message: string };
        expect(err.name).toBe('HttpError');
        expect(err.status).toBe(400);
        expect(err.message).toBe('Bad request');
      }
    });

    it('throws HttpError with correct status for 403', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: 'Forbidden' }),
      });

      api.setToken('token');
      try {
        await api.getProjects();
        expect.fail('Expected HttpError to be thrown');
      } catch (e: unknown) {
        const err = e as { name: string; status: number };
        expect(err.name).toBe('HttpError');
        expect(err.status).toBe(403);
      }
    });

    it('throws HttpError with status for JSON parse failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      api.setToken('token');
      try {
        await api.getProjects();
        expect.fail('Expected HttpError to be thrown');
      } catch (e: unknown) {
        const err = e as { name: string; status: number; message: string };
        expect(err.name).toBe('HttpError');
        expect(err.status).toBe(502);
        expect(err.message).toBe('An unexpected error occurred');
      }
    });
  });

  describe('Auth Endpoints', () => {
    it('register sends POST to /auth/register', async () => {
      const userData = { id: '1', email: 'new@example.com', first_name: 'New', last_name: null, photo_url: null, created_at: '' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(userData),
      });

      const result = await api.register({
        email: 'new@example.com',
        password: 'password123',
        first_name: 'New',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/register'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            email: 'new@example.com',
            password: 'password123',
            first_name: 'New',
          }),
        })
      );
      expect(result).toEqual(userData);
    });

    it('login sends form-urlencoded POST and stores token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ access_token: 'new-token', token_type: 'bearer' }),
      });

      const result = await api.login('user@example.com', 'password123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/login'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
      );
      expect(result.access_token).toBe('new-token');
      expect(api.getToken()).toBe('new-token');
    });

    it('login throws on invalid credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Invalid credentials' }),
      });

      await expect(api.login('wrong@example.com', 'wrong')).rejects.toThrow('Invalid credentials');
    });

    it('logout clears token', () => {
      api.setToken('token-to-clear');
      api.logout();
      expect(api.getToken()).toBeNull();
    });
  });

  describe('User Endpoints', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('getCurrentUser fetches /users/me', async () => {
      const user = { id: '1', email: 'me@example.com' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(user),
      });

      const result = await api.getCurrentUser();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me'),
        expect.objectContaining({ headers: expect.any(Object) })
      );
      expect(result).toEqual(user);
    });

    it('updateCurrentUser sends PUT to /users/me', async () => {
      const updatedUser = { id: '1', first_name: 'Updated' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(updatedUser),
      });

      await api.updateCurrentUser({ first_name: 'Updated' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ first_name: 'Updated' }),
        })
      );
    });

    it('changePassword sends PUT to /users/me/password', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.changePassword({ current_password: 'old', new_password: 'new' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me/password'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ current_password: 'old', new_password: 'new' }),
        })
      );
    });

    it('deleteAccount sends DELETE to /users/me', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deleteAccount();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('uploadPhoto sends multipart/form-data POST', async () => {
      const updatedUser = { id: '1', photo_url: 'https://example.com/photo.jpg' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(updatedUser),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await api.uploadPhoto(file);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me/photo'),
        expect.objectContaining({
          method: 'POST',
          headers: { Authorization: 'Bearer valid-token' },
        })
      );
      const [, options] = mockFetch.mock.calls[0];
      expect(options.body).toBeInstanceOf(FormData);
    });

    it('deletePhoto sends DELETE to /users/me/photo', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deletePhoto();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/users/me/photo'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Project Endpoints', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('getProjects fetches /projects', async () => {
      const projects = [{ id: '1', name: 'Project 1' }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(projects),
      });

      const result = await api.getProjects();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects'),
        expect.any(Object)
      );
      expect(result).toEqual(projects);
    });

    it('getProject fetches /projects/:id', async () => {
      const project = { id: '123', name: 'Single Project' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(project),
      });

      const result = await api.getProject('123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/123'),
        expect.any(Object)
      );
      expect(result).toEqual(project);
    });

    it('createProject sends POST to /projects', async () => {
      const newProject = { id: '1', name: 'New Project' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(newProject),
      });

      const result = await api.createProject({
        name: 'New Project',
        scale_min: 0,
        scale_max: 100,
        scale_unit: '%',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects'),
        expect.objectContaining({
          method: 'POST',
        })
      );
      expect(result).toEqual(newProject);
    });

    it('updateProject sends PUT to /projects/:id', async () => {
      const updated = { id: '1', name: 'Updated Project' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(updated),
      });

      await api.updateProject('1', { name: 'Updated Project' });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/1'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ name: 'Updated Project' }),
        })
      );
    });

    it('deleteProject sends DELETE to /projects/:id', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deleteProject('1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Invitation Endpoints', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('inviteExpert sends POST to /projects/:id/invite', async () => {
      const invitation = { id: 'inv-1', project_id: 'proj-1' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(invitation),
      });

      await api.inviteExpert('proj-1', 'expert@example.com');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/invite'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'expert@example.com' }),
        })
      );
    });

    it('getInvitations fetches /invitations', async () => {
      const invitations = [{ id: 'inv-1' }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(invitations),
      });

      const result = await api.getInvitations();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/invitations'),
        expect.any(Object)
      );
      expect(result).toEqual(invitations);
    });

    it('acceptInvitation sends POST to /invitations/:id/accept', async () => {
      const project = { id: 'proj-1' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(project),
      });

      await api.acceptInvitation('inv-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/invitations/inv-1/accept'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('declineInvitation sends POST to /invitations/:id/decline', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.declineInvitation('inv-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/invitations/inv-1/decline'),
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  describe('Member Endpoints', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('getMembers fetches /projects/:id/members', async () => {
      const members = [{ user_id: '1', role: 'admin' }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(members),
      });

      const result = await api.getMembers('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/members'),
        expect.any(Object)
      );
      expect(result).toEqual(members);
    });

    it('removeMember sends DELETE to /projects/:id/members/:userId', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.removeMember('proj-1', 'user-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/members/user-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Opinion Endpoints', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('getOpinions fetches /projects/:id/opinions', async () => {
      const opinions = [{ id: 'op-1', lower_bound: 30 }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(opinions),
      });

      const result = await api.getOpinions('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/opinions'),
        expect.any(Object)
      );
      expect(result).toEqual(opinions);
    });

    it('createOrUpdateOpinion sends POST to /projects/:id/opinions', async () => {
      const opinion = { id: 'op-1', lower_bound: 30, peak: 50, upper_bound: 70 };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(opinion),
      });

      await api.createOrUpdateOpinion('proj-1', {
        lower_bound: 30,
        peak: 50,
        upper_bound: 70,
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/opinions'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ lower_bound: 30, peak: 50, upper_bound: 70 }),
        })
      );
    });

    it('deleteOpinion sends DELETE to /projects/:id/opinions', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
      });

      await api.deleteOpinion('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/opinions'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Upload Photo Error Handling', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('throws error on uploadPhoto 500 response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Server error' }),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await expect(api.uploadPhoto(file)).rejects.toThrow('Server error');
    });

    it('redirects to /login and clears token on uploadPhoto 401', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await expect(api.uploadPhoto(file)).rejects.toThrow();
      expect(api.getToken()).toBeNull();
      expect(window.location.href).toBe('/login');
    });

    it('handles uploadPhoto JSON parse failure gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await expect(api.uploadPhoto(file)).rejects.toThrow('Upload failed');
    });

    it('omits Authorization header when no token for uploadPhoto', async () => {
      api.setToken(null);
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: '1', photo_url: 'url' }),
      });

      const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
      await api.uploadPhoto(file);

      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers['Authorization']).toBeUndefined();
    });
  });

  describe('Error Detail Edge Cases', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('falls back to "Validation error" when detail is empty array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: [] }),
      });

      await expect(api.getProjects()).rejects.toThrow('Validation error');
    });

    it('falls back to "Validation error" when detail array item has no msg', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({
          detail: [{ loc: ['body'], type: 'value_error' }],
        }),
      });

      await expect(api.getProjects()).rejects.toThrow('Validation error');
    });
  });

  describe('Login Error Edge Cases', () => {
    it('handles login JSON parse failure gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      await expect(api.login('user@example.com', 'pass')).rejects.toThrow('Invalid credentials');
    });

    it('falls back to "Login failed" when error.detail is empty', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: '' }),
      });

      await expect(api.login('user@example.com', 'pass')).rejects.toThrow('Login failed');
    });
  });

  describe('Results Endpoint', () => {
    beforeEach(() => {
      api.setToken('valid-token');
    });

    it('getResult fetches /projects/:id/result', async () => {
      const result = { best_compromise: { lower: 30, peak: 50, upper: 70 } };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(result),
      });

      const data = await api.getResult('proj-1');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj-1/result'),
        expect.any(Object)
      );
      expect(data).toEqual(result);
    });

    it('getResult returns null on error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: 'Not enough opinions' }),
      });

      const data = await api.getResult('proj-1');
      expect(data).toBeNull();
    });
  });
});
