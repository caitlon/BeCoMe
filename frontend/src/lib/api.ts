import {
  User,
  AuthResponse,
  Project,
  ProjectWithRole,
  Opinion,
  CalculationResult,
  Invitation,
  Member,
  ProjectInvitation,
  CreateProjectInput,
  UpdateProjectInput,
  CreateOpinionInput,
  RegisterInput,
  UpdateUserInput,
  ChangePasswordInput,
  ApiError,
} from '@/types/api';
import { logger } from '@/lib/logger';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export class HttpError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'HttpError';
  }
}

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('become_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('become_token', token);
    } else {
      localStorage.removeItem('become_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const requestId = crypto.randomUUID();
    const method = options.method ?? 'GET';
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'X-Request-ID': requestId,
      ...options.headers,
    };

    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }

    logger.debug('API request', { method, endpoint, requestId });

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        this.setToken(null);
        globalThis.location.href = '/login';
      }

      const error: ApiError = await response.json().catch(() => ({
        detail: 'An unexpected error occurred',
      }));

      const detail =
        typeof error.detail === 'string'
          ? error.detail
          : error.detail[0]?.msg || 'Validation error';
      logger.error('API error', { method, endpoint, status: response.status, requestId, detail });

      throw new HttpError(detail, response.status);
    }

    logger.debug('API response', { method, endpoint, status: response.status, requestId });

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  // Auth
  async register(data: RegisterInput): Promise<User> {
    return this.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async login(email: string, password: string): Promise<AuthResponse> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: 'Invalid credentials',
      }));
      logger.error('Login failed', { status: response.status });
      throw new Error(error.detail || 'Login failed');
    }

    const data: AuthResponse = await response.json();
    this.setToken(data.access_token);
    return data;
  }

  logout() {
    this.setToken(null);
  }

  async forgotPassword(email: string): Promise<void> {
    return this.request<void>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async resetPassword(token: string, newPassword: string): Promise<void> {
    return this.request<void>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    });
  }

  // Users
  async getCurrentUser(): Promise<User> {
    return this.request<User>('/users/me');
  }

  async updateCurrentUser(data: UpdateUserInput): Promise<User> {
    return this.request<User>('/users/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async changePassword(data: ChangePasswordInput): Promise<void> {
    return this.request<void>('/users/me/password', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteAccount(): Promise<void> {
    return this.request<void>('/users/me', {
      method: 'DELETE',
    });
  }

  async uploadPhoto(file: File): Promise<User> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: HeadersInit = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}/users/me/photo`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 401) {
        this.setToken(null);
        globalThis.location.href = '/login';
      }
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      logger.error('Photo upload failed', { status: response.status });
      throw new Error(error.detail || 'Failed to upload photo');
    }

    return response.json();
  }

  async deletePhoto(): Promise<void> {
    return this.request<void>('/users/me/photo', {
      method: 'DELETE',
    });
  }

  // Projects
  async getProjects(): Promise<ProjectWithRole[]> {
    return this.request<ProjectWithRole[]>('/projects');
  }

  async getProject(id: string): Promise<ProjectWithRole> {
    return this.request<ProjectWithRole>(`/projects/${id}`);
  }

  async createProject(data: CreateProjectInput): Promise<Project> {
    return this.request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateProject(id: string, data: UpdateProjectInput): Promise<Project> {
    return this.request<Project>(`/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteProject(id: string): Promise<void> {
    return this.request<void>(`/projects/${id}`, {
      method: 'DELETE',
    });
  }

  // Invitations
  async inviteExpert(projectId: string, email: string): Promise<Invitation> {
    return this.request<Invitation>(`/projects/${projectId}/invite`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async getInvitations(): Promise<Invitation[]> {
    return this.request<Invitation[]>('/invitations');
  }

  async acceptInvitation(invitationId: string): Promise<Project> {
    return this.request<Project>(`/invitations/${invitationId}/accept`, {
      method: 'POST',
    });
  }

  async declineInvitation(invitationId: string): Promise<void> {
    return this.request<void>(`/invitations/${invitationId}/decline`, {
      method: 'POST',
    });
  }

  // Project invitations
  async getProjectInvitations(projectId: string): Promise<ProjectInvitation[]> {
    return this.request<ProjectInvitation[]>(`/projects/${projectId}/invitations`);
  }

  // Members
  async getMembers(projectId: string): Promise<Member[]> {
    return this.request<Member[]>(`/projects/${projectId}/members`);
  }

  async removeMember(projectId: string, userId: string): Promise<void> {
    return this.request<void>(`/projects/${projectId}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  // Opinions
  async getOpinions(projectId: string): Promise<Opinion[]> {
    return this.request<Opinion[]>(`/projects/${projectId}/opinions`);
  }

  async createOrUpdateOpinion(
    projectId: string,
    data: CreateOpinionInput
  ): Promise<Opinion> {
    return this.request<Opinion>(`/projects/${projectId}/opinions`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteOpinion(projectId: string): Promise<void> {
    return this.request<void>(`/projects/${projectId}/opinions`, {
      method: 'DELETE',
    });
  }

  // Results
  async getResult(projectId: string): Promise<CalculationResult | null> {
    try {
      return await this.request<CalculationResult>(`/projects/${projectId}/result`);
    } catch (error) {
      logger.warn('Failed to fetch calculation result', {
        projectId,
        error: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }
}

export const api = new ApiClient();
