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
  ProjectDisposition,
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

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function readCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    silent = false
  ): Promise<T> {
    const requestId = crypto.randomUUID();
    const method = options.method ?? 'GET';
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Request-ID': requestId,
      ...(options.headers as Record<string, string>),
    };

    // Cookie-based session: echo the readable csrf_token cookie on mutating requests.
    if (MUTATING_METHODS.has(method.toUpperCase())) {
      const csrf = readCsrfToken();
      if (csrf) {
        headers['X-CSRF-Token'] = csrf;
      }
    }

    logger.debug('API request', { method, endpoint, requestId });

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      credentials: 'include',
      headers,
    });

    if (!response.ok) {
      // A session-expiry 401 sends the user to login; the mount-time auth probe passes
      // silent=true so an anonymous visitor on a public page is not bounced there.
      if (response.status === 401 && !silent) {
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
      credentials: 'include',
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

    // The session now lives in HttpOnly cookies set by the server; the body token is
    // ignored here and kept only for programmatic (non-browser) clients.
    return response.json();
  }

  async logout(): Promise<void> {
    // Hit the server so it revokes the session and clears the HttpOnly cookies.
    try {
      await this.request<void>('/auth/logout', { method: 'POST' });
    } catch {
      // Ignore: the user is logging out regardless of a network hiccup.
    }
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
  async getCurrentUser(silent = false): Promise<User> {
    return this.request<User>('/users/me', {}, silent);
  }

  // Returns the user's full GDPR data export. The payload is only downloaded as
  // a file (never rendered), so it stays an opaque record instead of mirroring
  // the backend schema and risking drift.
  async exportData(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/users/me/export');
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

  async deleteAccount(dispositions: ProjectDisposition[] = []): Promise<void> {
    return this.request<void>('/users/me', {
      method: 'DELETE',
      body: JSON.stringify({ project_dispositions: dispositions }),
    });
  }

  async uploadPhoto(file: File): Promise<User> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    const csrf = readCsrfToken();
    if (csrf) {
      headers['X-CSRF-Token'] = csrf;
    }

    const response = await fetch(`${API_BASE_URL}/users/me/photo`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 401) {
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

  async transferOwnership(projectId: string, newAdminId: string): Promise<Project> {
    return this.request<Project>(`/projects/${projectId}/transfer-ownership`, {
      method: 'POST',
      body: JSON.stringify({ new_admin_id: newAdminId }),
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

  // Downloads a project's BeCoMe result as a PDF or CSV file. Bearer auth means
  // it is fetched as a blob and saved client-side rather than via a plain link.
  async exportProjectResult(
    projectId: string,
    format: 'pdf' | 'csv',
    lang: string
  ): Promise<Blob> {
    const headers: Record<string, string> = { 'X-Request-ID': crypto.randomUUID() };

    const response = await fetch(
      `${API_BASE_URL}/projects/${projectId}/result/export?format=${format}&lang=${lang}`,
      { credentials: 'include', headers }
    );

    if (!response.ok) {
      if (response.status === 401) {
        globalThis.location.href = '/login';
      }
      const error = await response.json().catch(() => ({ detail: 'Export failed' }));
      const detail = typeof error.detail === 'string' ? error.detail : 'Export failed';
      logger.error('Result export failed', {
        projectId,
        format,
        status: response.status,
      });
      throw new HttpError(detail, response.status);
    }

    return response.blob();
  }
}

export const api = new ApiClient();
