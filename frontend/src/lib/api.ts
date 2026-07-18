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
import {
  HttpError,
  NetworkError,
  UnauthorizedError,
  ForbiddenError,
  RateLimitError,
  ServerError,
  isUnauthorized,
  isServiceUnavailable,
} from '@/lib/errors';

export { HttpError } from '@/lib/errors';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function readCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Reads the `detail` field off an error response body, matching FastAPI's
 * error shape: either a plain string, or a validation array whose first
 * entry's `msg` is shown.
 *
 * An unparseable body (not JSON at all) gets the generic fallback text,
 * since nothing about the failure is known at that point. A body that
 * parses fine but simply omits `detail` returns an empty string instead,
 * so callers building a typed error can fall back to that error class's
 * own, more specific default message.
 */
export async function parseDetail(response: Response): Promise<string> {
  const error: ApiError | undefined = await response.json().catch(() => undefined);

  if (error === undefined) {
    return 'An unexpected error occurred';
  }
  if (typeof error.detail === 'string') {
    return error.detail;
  }
  if (Array.isArray(error.detail)) {
    return error.detail[0]?.msg || 'Validation error';
  }
  return '';
}

/** Classifies a non-ok response into the typed error taxonomy. */
export async function toHttpError(response: Response): Promise<HttpError> {
  const detail = await parseDetail(response);
  const message = detail || undefined;

  if (response.status === 401) {
    return new UnauthorizedError(message);
  }
  if (response.status === 403) {
    return new ForbiddenError(message);
  }
  if (response.status === 429) {
    const retryAfterHeader = response.headers.get('Retry-After');
    const retryAfter = retryAfterHeader ? Number(retryAfterHeader) : undefined;
    return new RateLimitError(message, retryAfter);
  }
  if (response.status >= 500) {
    return new ServerError(message, response.status);
  }
  return new HttpError(detail || 'An unexpected error occurred', response.status);
}

/** Wraps fetch() so a network-level failure (offline, DNS, CORS) surfaces as a NetworkError. */
export async function safeFetch(input: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : 'Network request failed';
    throw new NetworkError(message, { cause });
  }
}

class ApiClient {
  private refreshInFlight: Promise<void> | null = null;
  private sessionExpiredNotified = false;
  private onSessionExpired: (() => void) | null = null;

  /** Registers the callback fired when a session cannot be recovered by a silent refresh. */
  setOnSessionExpired(fn: (() => void) | null): void {
    this.sessionExpiredNotified = false;
    this.onSessionExpired = fn;
  }

  /**
   * Refreshes the session via the HttpOnly refresh cookie. Concurrent callers
   * share a single in-flight request instead of each firing their own POST.
   */
  private refreshSession(): Promise<void> {
    this.refreshInFlight ??= (async () => {
      const res = await safeFetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-Request-ID': crypto.randomUUID() },
      });
      if (!res.ok) {
        throw await toHttpError(res);
      }
    })().finally(() => {
      this.refreshInFlight = null;
    });
    return this.refreshInFlight;
  }

  /**
   * A 401 that survives a silent-refresh attempt is terminal: log it, and for
   * anything other than the mount-time auth probe, tell subscribers the
   * session is gone so they can react (clear user state, show a toast).
   *
   * Notification is idempotent: concurrent requests can all land here for the
   * same expired session, but onSessionExpired should fire once, not once per
   * request. sessionExpiredNotified latches after the first call and is
   * cleared again by setOnSessionExpired (new subscriber) or by the next
   * successful response (the session is alive again, so a future expiry is a
   * new event worth notifying about).
   */
  private handleTerminalUnauthorized(isAuthProbe: boolean, endpoint: string): void {
    logger.debug('Session unauthorized', { endpoint, isAuthProbe });
    if (isAuthProbe) return;
    if (this.sessionExpiredNotified) return;
    this.sessionExpiredNotified = true;
    this.onSessionExpired?.();
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    opts: { isAuthProbe?: boolean; isRetry?: boolean } = {}
  ): Promise<T> {
    const { isAuthProbe = false, isRetry = false } = opts;
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

    const response = await safeFetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      credentials: 'include',
      headers,
    });

    if (!response.ok) {
      // A 401 gets one silent-refresh-and-retry attempt before it is treated as
      // terminal. isAuthProbe only changes what happens once refresh also fails:
      // a probe (mount-time "am I logged in?" check) stays silent, everything
      // else notifies onSessionExpired.
      if (response.status === 401 && !isRetry) {
        try {
          await this.refreshSession();
        } catch (refreshError) {
          // A network/5xx refresh failure means the service is down, not that the
          // session is gone -- surface the typed error (so react-query can retry
          // and AuthContext shows "service unavailable") instead of a false logout.
          if (isServiceUnavailable(refreshError)) {
            throw refreshError;
          }
          this.handleTerminalUnauthorized(isAuthProbe, endpoint);
          throw new UnauthorizedError();
        }
        return this.request<T>(endpoint, options, { isAuthProbe, isRetry: true });
      }

      const error = await toHttpError(response);
      if (isUnauthorized(error)) {
        this.handleTerminalUnauthorized(isAuthProbe, endpoint);
      } else {
        logger.error('API error', {
          method,
          endpoint,
          status: error.status,
          requestId,
          detail: error.message,
        });
      }

      throw error;
    }

    this.sessionExpiredNotified = false;

    logger.debug('API response', { method, endpoint, status: response.status, requestId });

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  /**
   * Shared 401-retry-with-refresh wrapper for the two endpoints that build
   * their own fetch calls instead of going through request() (FormData/Blob
   * bodies do not fit the JSON request() contract). Returns the raw Response
   * either way so the caller keeps its own success parsing (.json()/.blob())
   * and its own non-401 error fallback text.
   *
   * buildInit is a thunk rather than a static RequestInit so a retry after a
   * successful refresh reads a fresh CSRF token and request ID, not stale ones
   * captured before the refresh ran.
   */
  private async fetchWithRefresh(
    input: string,
    buildInit: () => RequestInit
  ): Promise<Response> {
    const response = await safeFetch(input, buildInit());

    if (response.status !== 401) {
      if (response.ok) {
        this.sessionExpiredNotified = false;
      }
      return response;
    }

    try {
      await this.refreshSession();
    } catch (refreshError) {
      if (isServiceUnavailable(refreshError)) {
        throw refreshError;
      }
      this.handleTerminalUnauthorized(false, input);
      return response;
    }

    const retried = await safeFetch(input, buildInit());
    if (retried.status === 401) {
      this.handleTerminalUnauthorized(false, input);
    }
    if (retried.ok) {
      this.sessionExpiredNotified = false;
    }
    return retried;
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

    const response = await safeFetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      logger.error('Login failed', { status: response.status });
      throw await toHttpError(response);
    }

    // The session now lives in HttpOnly cookies set by the server; the body token is
    // ignored here and kept only for programmatic (non-browser) clients.
    return response.json();
  }

  async logout(): Promise<void> {
    // Hit the server so it revokes the session and clears the HttpOnly cookies.
    try {
      await this.request<void>('/auth/logout', { method: 'POST' }, { isAuthProbe: true });
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
  async getCurrentUser(isAuthProbe = false): Promise<User> {
    return this.request<User>('/users/me', {}, { isAuthProbe });
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

    const response = await this.fetchWithRefresh(`${API_BASE_URL}/users/me/photo`, () => {
      const headers: Record<string, string> = { 'X-Request-ID': crypto.randomUUID() };
      const csrf = readCsrfToken();
      if (csrf) {
        headers['X-CSRF-Token'] = csrf;
      }
      return { method: 'POST', credentials: 'include', headers, body: formData };
    });

    if (!response.ok) {
      logger.error('Photo upload failed', { status: response.status });
      throw await toHttpError(response);
    }

    return response.json();
  }

  async deletePhoto(): Promise<void> {
    return this.request<void>('/users/me/photo', {
      method: 'DELETE',
    });
  }

  // Projects
  async getProjects(params?: { limit?: number; offset?: number }): Promise<ProjectWithRole[]> {
    const query = new URLSearchParams();
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    if (params?.offset !== undefined) query.set('offset', String(params.offset));
    const suffix = query.size > 0 ? `?${query.toString()}` : '';
    return this.request<ProjectWithRole[]>(`/projects${suffix}`);
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
    const url = `${API_BASE_URL}/projects/${projectId}/result/export?format=${format}&lang=${lang}`;
    const response = await this.fetchWithRefresh(url, () => ({
      credentials: 'include',
      headers: { 'X-Request-ID': crypto.randomUUID() },
    }));

    if (!response.ok) {
      logger.error('Result export failed', { projectId, format, status: response.status });
      throw await toHttpError(response);
    }

    return response.blob();
  }
}

export const api = new ApiClient();
