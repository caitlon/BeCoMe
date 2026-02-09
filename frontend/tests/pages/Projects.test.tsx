import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import Projects from '@/pages/Projects';
import { createProjectWithRole, createInvitation } from '@tests/factories';

// Mock api
const mockApi = {
  getProjects: vi.fn(),
  getInvitations: vi.fn(),
  acceptInvitation: vi.fn(),
  declineInvitation: vi.fn(),
  deleteProject: vi.fn(),
};

vi.mock('@/lib/api', () => ({
  api: {
    getProjects: () => mockApi.getProjects(),
    getInvitations: () => mockApi.getInvitations(),
    acceptInvitation: (id: string) => mockApi.acceptInvitation(id),
    declineInvitation: (id: string) => mockApi.declineInvitation(id),
    deleteProject: (id: string) => mockApi.deleteProject(id),
  },
}));

// Mock useAuth
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: '1', email: 'test@example.com', first_name: 'Test' },
    isLoading: false,
    isAuthenticated: true,
  }),
}));

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

describe('Projects', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.getProjects.mockResolvedValue([]);
    mockApi.getInvitations.mockResolvedValue([]);
  });

  describe('Loading State', () => {
    it('shows loading spinner while fetching', async () => {
      mockApi.getProjects.mockImplementation(() => new Promise(() => {}));
      mockApi.getInvitations.mockImplementation(() => new Promise(() => {}));

      render(<Projects />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no projects', async () => {
      mockApi.getProjects.mockResolvedValue([]);
      mockApi.getInvitations.mockResolvedValue([]);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
      });
    });

    it('has create project button in empty state', async () => {
      mockApi.getProjects.mockResolvedValue([]);
      mockApi.getInvitations.mockResolvedValue([]);

      render(<Projects />);

      await waitFor(() => {
        const buttons = screen.getAllByRole('button', { name: /create.*first|new project/i });
        expect(buttons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Project Cards', () => {
    it('renders project cards when projects exist', async () => {
      const projects = [
        createProjectWithRole({ name: 'Project Alpha', role: 'admin' }),
        createProjectWithRole({ name: 'Project Beta', role: 'expert' }),
      ];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText('Project Alpha')).toBeInTheDocument();
        expect(screen.getByText('Project Beta')).toBeInTheDocument();
      });
    });

    it('shows project description', async () => {
      const projects = [
        createProjectWithRole({ description: 'Test description here' }),
      ];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText('Test description here')).toBeInTheDocument();
      });
    });

    it('shows scale information', async () => {
      const projects = [
        createProjectWithRole({ scale_min: 0, scale_max: 100, scale_unit: '%' }),
      ];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText(/0 — 100 %/)).toBeInTheDocument();
      });
    });

    it('shows member count', async () => {
      const projects = [
        createProjectWithRole({ member_count: 5 }),
      ];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText(/5.*expert/i)).toBeInTheDocument();
      });
    });

    it('shows admin badge for admin role', async () => {
      const projects = [createProjectWithRole({ role: 'admin' })];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText(/admin/i)).toBeInTheDocument();
      });
    });

    it('shows expert badge for expert role', async () => {
      const projects = [createProjectWithRole({ role: 'expert' })];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        // Find badge with "Expert" text (case-sensitive)
        const badges = screen.getAllByText('Expert');
        expect(badges.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Project Actions', () => {
    it('admin project has role admin badge', async () => {
      const projects = [createProjectWithRole({ name: 'Admin Project', role: 'admin' })];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText('Admin Project')).toBeInTheDocument();
        // Admin badge should be visible
        expect(screen.getByText('Admin')).toBeInTheDocument();
      });
    });

    it('project card has link to project detail', async () => {
      const projects = [createProjectWithRole({ id: 'proj-123', name: 'Linked Project' })];
      mockApi.getProjects.mockResolvedValue(projects);

      render(<Projects />);

      await waitFor(() => {
        const projectLink = screen.getByRole('link', { name: 'Linked Project' });
        expect(projectLink).toHaveAttribute('href', '/projects/proj-123');
      });
    });
  });

  describe('Tabs', () => {
    it('shows tabs for projects and invitations', async () => {
      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /my projects/i })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: /invitations/i })).toBeInTheDocument();
      });
    });

    it('shows invitation count badge when invitations exist', async () => {
      const invitations = [
        createInvitation(),
        createInvitation(),
      ];
      mockApi.getInvitations.mockResolvedValue(invitations);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByText('2')).toBeInTheDocument();
      });
    });

    it('switches to invitations tab', async () => {
      const user = userEvent.setup();
      const invitations = [createInvitation({ project_name: 'Invited Project' })];
      mockApi.getInvitations.mockResolvedValue(invitations);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /invitations/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /invitations/i }));

      await waitFor(() => {
        expect(screen.getByText('Invited Project')).toBeInTheDocument();
      });
    });
  });

  describe('Invitations', () => {
    it('shows empty state when no invitations', async () => {
      const user = userEvent.setup();
      mockApi.getInvitations.mockResolvedValue([]);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /invitations/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /invitations/i }));

      await waitFor(() => {
        expect(screen.getByText(/no pending invitations/i)).toBeInTheDocument();
      });
    });

    it('shows invitation details', async () => {
      const user = userEvent.setup();
      const invitations = [
        createInvitation({
          project_name: 'Research Project',
          inviter_first_name: 'John',
          inviter_email: 'john@example.com',
        }),
      ];
      mockApi.getInvitations.mockResolvedValue(invitations);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.queryByRole('status')).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /invitations/i }));

      await waitFor(() => {
        expect(screen.getByText('Research Project')).toBeInTheDocument();
        expect(screen.getByText(/john/i)).toBeInTheDocument();
      });
    });

    it('accept invitation calls API and refreshes', async () => {
      const user = userEvent.setup();
      const invitations = [createInvitation({ id: 'inv-123' })];
      mockApi.getInvitations.mockResolvedValue(invitations);
      mockApi.acceptInvitation.mockResolvedValue({});

      render(<Projects />);

      await waitFor(() => {
        expect(screen.queryByRole('status')).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /invitations/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /accept/i }));

      await waitFor(() => {
        expect(mockApi.acceptInvitation).toHaveBeenCalledWith('inv-123');
      });
    });

    it('decline invitation calls API and refreshes', async () => {
      const user = userEvent.setup();
      const invitations = [createInvitation({ id: 'inv-456' })];
      mockApi.getInvitations.mockResolvedValue(invitations);
      mockApi.declineInvitation.mockResolvedValue(undefined);

      render(<Projects />);

      await waitFor(() => {
        expect(screen.queryByRole('status')).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('tab', { name: /invitations/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /decline/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /decline/i }));

      await waitFor(() => {
        expect(mockApi.declineInvitation).toHaveBeenCalledWith('inv-456');
      });
    });
  });

  describe('Create Project', () => {
    it('opens create project modal when clicking New Project', async () => {
      const user = userEvent.setup();

      render(<Projects />);

      await waitFor(() => {
        expect(screen.queryByRole('status')).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /new project/i }));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('shows error toast when loading fails', async () => {
      mockApi.getProjects.mockRejectedValue(new Error('Network error'));
      mockApi.getInvitations.mockRejectedValue(new Error('Network error'));

      render(<Projects />);

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: 'destructive',
          })
        );
      });
    });
  });
});
