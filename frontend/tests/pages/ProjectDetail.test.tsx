import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import ProjectDetail from '@/pages/ProjectDetail';
import { HttpError } from '@/lib/api';
import {
  createProject,
  createProjectWithRole,
  createOpinion,
  createMember,
  createCalculationResult,
} from '@tests/factories/project';

// Use vi.hoisted for mock variables
const { mockApi, mockToast, mockUser, mockNavigate, mockDownloadBlob } = vi.hoisted(() => ({
  mockApi: {
    getProject: vi.fn(),
    getOpinions: vi.fn(),
    getResult: vi.fn(),
    getMembers: vi.fn(),
    getProjectInvitations: vi.fn(),
    createOrUpdateOpinion: vi.fn(),
    deleteOpinion: vi.fn(),
    deleteProject: vi.fn(),
    removeMember: vi.fn(),
    transferOwnership: vi.fn(),
    exportProjectResult: vi.fn(),
  },
  mockToast: vi.fn(),
  mockDownloadBlob: vi.fn(),
  mockUser: {
    id: 'user-1',
    email: 'john@example.com',
    first_name: 'John',
    last_name: 'Doe',
    photo_url: null,
    created_at: '2024-01-01T00:00:00Z',
  },
  mockNavigate: vi.fn(),
}));

// Mock useParams
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useParams: () => ({ id: 'project-1' }),
    useNavigate: () => mockNavigate,
  };
});

// Mock api (keep HttpError from original module)
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    api: mockApi,
    HttpError: actual.HttpError,
  };
});

// Mock useToast
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock the download helper so clicking export does not touch DOM/URL APIs
vi.mock('@/lib/download', () => ({
  downloadBlob: mockDownloadBlob,
  downloadJson: vi.fn(),
}));

// Mock useAuth
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
  }),
}));

// Drive the responsive layout deterministically. The page renders a single
// layout for the active breakpoint, so tests choose desktop (grid + collapsible
// team) or mobile (tabs) by flipping this flag instead of relying on both
// layouts coexisting in the DOM.
const { mediaState } = vi.hoisted(() => ({ mediaState: { isDesktop: true } }));
vi.mock('@/hooks/use-media-query', () => ({
  useMediaQuery: () => mediaState.isDesktop,
}));

// Filter out framer-motion props
const filterMotionProps = (props: Record<string, unknown>) => {
  const motionProps = ['initial', 'animate', 'exit', 'variants', 'transition', 'whileHover', 'whileTap', 'whileInView', 'viewport'];
  const filtered: Record<string, unknown> = {};
  for (const key of Object.keys(props)) {
    if (!motionProps.includes(key)) {
      filtered[key] = props[key];
    }
  }
  return filtered;
};

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...filterMotionProps(props)}>{children}</div>
    ),
    nav: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <nav {...filterMotionProps(props)}>{children}</nav>
    ),
    span: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <span {...filterMotionProps(props)}>{children}</span>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren<object>) => <>{children}</>,
}));

// Reset to the desktop layout before every test; mobile-specific tests opt in.
beforeEach(() => {
  mediaState.isDesktop = true;
});

const defaultSetup = () => {
  const project = createProjectWithRole({
    id: 'project-1',
    name: 'Test Project',
    description: 'Test Description',
    role: 'admin',
  });

  mockApi.getProject.mockResolvedValue(project);
  mockApi.getOpinions.mockResolvedValue([]);
  mockApi.getResult.mockResolvedValue(null);
  mockApi.getMembers.mockResolvedValue([]);
  mockApi.getProjectInvitations.mockResolvedValue([]);

  return { project };
};

describe('ProjectDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('shows loading spinner initially', () => {
    // Don't resolve promises immediately
    mockApi.getProject.mockReturnValue(new Promise(() => {}));
    mockApi.getOpinions.mockReturnValue(new Promise(() => {}));
    mockApi.getResult.mockReturnValue(new Promise(() => {}));
    mockApi.getMembers.mockReturnValue(new Promise(() => {}));
    mockApi.getProjectInvitations.mockReturnValue(new Promise(() => {}));

    render(<ProjectDetail />);

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders project name and description', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
      expect(screen.getByText('Test Description')).toBeInTheDocument();
    });
  });

  it('renders scale information', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText(/Scale: 0 — 100 %/)).toBeInTheDocument();
    });
  });

  it('renders admin action buttons for admin users', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /invite experts/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
    });
  });

  it('hides admin buttons for expert users', async () => {
    mockApi.getProject.mockResolvedValue(createProjectWithRole({ role: 'expert' }));

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /invite experts/i })).not.toBeInTheDocument();
    });
  });

  it('renders back to projects link', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /projects/i })).toHaveAttribute('href', '/projects');
    });
  });

  it('explains that an example project team is fictional', async () => {
    mockApi.getProject.mockResolvedValue(
      createProjectWithRole({ id: 'project-1', role: 'admin', is_example: true }),
    );

    render(<ProjectDetail />);

    expect(await screen.findByText('This is an example project')).toBeInTheDocument();
  });

  it('shows no banner on an ordinary project', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
    expect(screen.queryByText('This is an example project')).not.toBeInTheDocument();
  });
});

describe('ProjectDetail - Opinion Form Prefill', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('pre-fills form with empty position when opinion has no position', async () => {
    const existingOpinion = createOpinion({
      user_id: 'user-1',
      position: '',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
    });
    mockApi.getOpinions.mockResolvedValue([existingOpinion]);

    render(<ProjectDetail />);

    await waitFor(() => {
      const positionInputs = screen.getAllByLabelText('Position');
      expect(positionInputs[0]).toHaveValue('');
    });
  });
});

describe('ProjectDetail - Team Section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('displays team member count', async () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /team.*2 members/i })).toBeInTheDocument();
    });
  });

  it('team section is expanded by default', async () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    // Team content should be visible without clicking the trigger (teamOpen defaults to true)
    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    // Collapsible trigger shows member count, and the section is already expanded
    expect(screen.getByRole('button', { name: /team.*2 members/i })).toBeInTheDocument();
  });

  it('can collapse team section', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /team.*2 members/i })).toBeInTheDocument();
    });

    // Click to collapse
    await user.click(screen.getByRole('button', { name: /team.*2 members/i }));

    // Team section should be collapsed after click
    await waitFor(() => {
      const trigger = screen.getByRole('button', { name: /team.*2 members/i });
      expect(trigger).toHaveAttribute('data-state', 'closed');
    });
  });

  it('transfers ownership to a member after confirmation', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.transferOwnership.mockResolvedValue(createProject({ id: 'project-1' }));

    render(<ProjectDetail />);

    // The "make owner" action is shown for non-admin members in the admin view
    const transferButtons = await screen.findAllByRole('button', {
      name: /make jane smith the owner/i,
    });
    await user.click(transferButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Transfer ownership?')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Transfer ownership' }));

    await waitFor(() => {
      expect(mockApi.transferOwnership).toHaveBeenCalledWith('project-1', 'user-2');
    });
  });
});

describe('ProjectDetail - Delete Project', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('opens delete confirmation modal', async () => {
    const user = userEvent.setup();
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /delete/i }));

    await waitFor(() => {
      expect(screen.getByText('Delete Project?')).toBeInTheDocument();
    });
  });
});

describe('ProjectDetail - Pending Invitations Fetch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('fetches project invitations on load', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(mockApi.getProjectInvitations).toHaveBeenCalledWith('project-1');
    });
  });
});

describe('ProjectDetail - Member Profile Dialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('opens profile dialog when clicking a member row', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    const memberRow = screen.getAllByRole('button', { name: /view profile of jane smith/i })[0];
    await user.click(memberRow);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Jane Smith' })).toBeInTheDocument();
    });
  });
});

describe('ProjectDetail - Invitations 403 handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders page normally when invitations endpoint returns 403', async () => {
    const project = createProjectWithRole({ id: 'project-1', name: 'Test Project', role: 'expert' });
    mockApi.getProject.mockResolvedValue(project);
    mockApi.getOpinions.mockResolvedValue([]);
    mockApi.getResult.mockResolvedValue(null);
    mockApi.getMembers.mockResolvedValue([]);
    mockApi.getProjectInvitations.mockRejectedValue(new HttpError('Forbidden', 403));

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
  });

  it('shows error toast and navigates away on non-403 invitation error', async () => {
    const project = createProjectWithRole({ id: 'project-1', name: 'Test Project', role: 'admin' });
    mockApi.getProject.mockResolvedValue(project);
    mockApi.getOpinions.mockResolvedValue([]);
    mockApi.getResult.mockResolvedValue(null);
    mockApi.getMembers.mockResolvedValue([]);
    mockApi.getProjectInvitations.mockRejectedValue(new HttpError('Server Error', 500));

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ variant: 'destructive' }),
      );
      expect(mockNavigate).toHaveBeenCalledWith('/projects');
    });
  });
});

describe('ProjectDetail - Opinion Form Validations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('blocks save and shows an inline error when peak > upper (order violation)', async () => {
    const user = userEvent.setup();
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Save Opinion' }).length).toBeGreaterThan(0);
    });

    const positionInputs = screen.getAllByLabelText('Position');
    await user.type(positionInputs[0], 'Manager');

    const lowerInputs = screen.getAllByLabelText(/lower/i);
    await user.type(lowerInputs[0], '20');

    const peakInputs = screen.getAllByLabelText(/peak/i);
    await user.type(peakInputs[0], '90');

    const upperInputs = screen.getAllByLabelText(/upper/i);
    await user.type(upperInputs[0], '80');

    const saveButtons = screen.getAllByRole('button', { name: 'Save Opinion' });
    await user.click(saveButtons[0]);

    await waitFor(() => {
      expect(
        screen.getAllByText('Values must satisfy: lower ≤ peak ≤ upper').length
      ).toBeGreaterThan(0);
    });
    expect(mockApi.createOrUpdateOpinion).not.toHaveBeenCalled();
  });

  it('blocks save and shows an inline error when lower > peak', async () => {
    const user = userEvent.setup();
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Save Opinion' }).length).toBeGreaterThan(0);
    });

    const positionInputs = screen.getAllByLabelText('Position');
    await user.type(positionInputs[0], 'Manager');

    const lowerInputs = screen.getAllByLabelText(/lower/i);
    await user.type(lowerInputs[0], '60');

    const peakInputs = screen.getAllByLabelText(/peak/i);
    await user.type(peakInputs[0], '40');

    const upperInputs = screen.getAllByLabelText(/upper/i);
    await user.type(upperInputs[0], '80');

    const saveButtons = screen.getAllByRole('button', { name: 'Save Opinion' });
    await user.click(saveButtons[0]);

    await waitFor(() => {
      expect(
        screen.getAllByText('Values must satisfy: lower ≤ peak ≤ upper').length
      ).toBeGreaterThan(0);
    });
    expect(mockApi.createOrUpdateOpinion).not.toHaveBeenCalled();
  });

  it('blocks save and shows an inline error when values outside scale range', async () => {
    const user = userEvent.setup();
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Save Opinion' }).length).toBeGreaterThan(0);
    });

    const positionInputs = screen.getAllByLabelText('Position');
    await user.type(positionInputs[0], 'Manager');

    // scale_min=0, scale_max=100. Use lower=-5 which is outside range
    const lowerInputs = screen.getAllByLabelText(/lower/i);
    await user.type(lowerInputs[0], '-5');

    const peakInputs = screen.getAllByLabelText(/peak/i);
    await user.type(peakInputs[0], '50');

    const upperInputs = screen.getAllByLabelText(/upper/i);
    await user.type(upperInputs[0], '80');

    const saveButtons = screen.getAllByRole('button', { name: 'Save Opinion' });
    await user.click(saveButtons[0]);

    await waitFor(() => {
      expect(
        screen.getAllByText('Values must be within scale range: 0 — 100').length
      ).toBeGreaterThan(0);
    });
    expect(mockApi.createOrUpdateOpinion).not.toHaveBeenCalled();
  });
});

describe('ProjectDetail - Opinion Save', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('saves opinion successfully and shows success toast', async () => {
    const user = userEvent.setup();
    mockApi.createOrUpdateOpinion.mockResolvedValue(undefined);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Save Opinion' }).length).toBeGreaterThan(0);
    });

    const positionInputs = screen.getAllByLabelText('Position');
    await user.type(positionInputs[0], 'Manager');

    const lowerInputs = screen.getAllByLabelText(/lower/i);
    await user.type(lowerInputs[0], '20');

    const peakInputs = screen.getAllByLabelText(/peak/i);
    await user.type(peakInputs[0], '50');

    const upperInputs = screen.getAllByLabelText(/upper/i);
    await user.type(upperInputs[0], '80');

    const saveButtons = screen.getAllByRole('button', { name: 'Save Opinion' });
    await user.click(saveButtons[0]);

    await waitFor(() => {
      expect(mockApi.createOrUpdateOpinion).toHaveBeenCalledWith('project-1', {
        position: 'Manager',
        lower_bound: 20,
        peak: 50,
        upper_bound: 80,
      });
      expect(mockToast).toHaveBeenCalledWith({ title: 'Opinion saved' });
    });
  });

  it('shows generic error toast when save fails with non-Error', async () => {
    const user = userEvent.setup();
    mockApi.createOrUpdateOpinion.mockRejectedValue('string error');

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Save Opinion' }).length).toBeGreaterThan(0);
    });

    const positionInputs = screen.getAllByLabelText('Position');
    await user.type(positionInputs[0], 'Manager');

    const lowerInputs = screen.getAllByLabelText(/lower/i);
    await user.type(lowerInputs[0], '20');

    const peakInputs = screen.getAllByLabelText(/peak/i);
    await user.type(peakInputs[0], '50');

    const upperInputs = screen.getAllByLabelText(/upper/i);
    await user.type(upperInputs[0], '80');

    const saveButtons = screen.getAllByRole('button', { name: 'Save Opinion' });
    await user.click(saveButtons[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to save',
          variant: 'destructive',
        }),
      );
    });
  });

  it('shows error toast when save fails with Error', async () => {
    const user = userEvent.setup();
    mockApi.createOrUpdateOpinion.mockRejectedValue(new Error('Network error'));

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Save Opinion' }).length).toBeGreaterThan(0);
    });

    const positionInputs = screen.getAllByLabelText('Position');
    await user.type(positionInputs[0], 'Manager');

    const lowerInputs = screen.getAllByLabelText(/lower/i);
    await user.type(lowerInputs[0], '20');

    const peakInputs = screen.getAllByLabelText(/peak/i);
    await user.type(peakInputs[0], '50');

    const upperInputs = screen.getAllByLabelText(/upper/i);
    await user.type(upperInputs[0], '80');

    const saveButtons = screen.getAllByRole('button', { name: 'Save Opinion' });
    await user.click(saveButtons[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Network error',
          variant: 'destructive',
        }),
      );
    });
  });
});

describe('ProjectDetail - Delete Opinion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('deletes opinion and clears form', async () => {
    const user = userEvent.setup();
    const existingOpinion = createOpinion({
      user_id: 'user-1',
      position: 'Manager',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
    });
    mockApi.getOpinions.mockResolvedValue([existingOpinion]);
    mockApi.deleteOpinion.mockResolvedValue(undefined);

    render(<ProjectDetail />);

    await waitFor(() => {
      const deleteButtons = screen.getAllByRole('button', { name: /delete my opinion/i });
      expect(deleteButtons.length).toBeGreaterThan(0);
    });

    const deleteButtons = screen.getAllByRole('button', { name: /delete my opinion/i });
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockApi.deleteOpinion).toHaveBeenCalledWith('project-1');
      expect(mockToast).toHaveBeenCalledWith({ title: 'Opinion deleted' });
    });
  });

  it('shows error toast when delete opinion fails', async () => {
    const user = userEvent.setup();
    const existingOpinion = createOpinion({
      user_id: 'user-1',
      position: 'Manager',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
    });
    mockApi.getOpinions.mockResolvedValue([existingOpinion]);
    mockApi.deleteOpinion.mockRejectedValue(new Error('Delete failed'));

    render(<ProjectDetail />);

    await waitFor(() => {
      const deleteButtons = screen.getAllByRole('button', { name: /delete my opinion/i });
      expect(deleteButtons.length).toBeGreaterThan(0);
    });

    const deleteButtons = screen.getAllByRole('button', { name: /delete my opinion/i });
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to delete opinion',
          variant: 'destructive',
        }),
      );
    });
  });
});

describe('ProjectDetail - Delete Project Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('deletes project successfully and navigates to projects', async () => {
    const user = userEvent.setup();
    mockApi.deleteProject.mockResolvedValue(undefined);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^delete$/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /^delete$/i }));

    await waitFor(() => {
      expect(screen.getByText('Delete Project?')).toBeInTheDocument();
    });

    const dialog = screen.getByRole('dialog');
    const confirmButton = within(dialog).getByRole('button', { name: /delete/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockApi.deleteProject).toHaveBeenCalledWith('project-1');
      expect(mockToast).toHaveBeenCalledWith({ title: 'Project deleted' });
      expect(mockNavigate).toHaveBeenCalledWith('/projects');
    });
  });

  it('shows error toast when delete project fails', async () => {
    const user = userEvent.setup();
    mockApi.deleteProject.mockRejectedValue(new Error('Delete failed'));

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^delete$/i })).toBeInTheDocument();
    });

    // Open delete modal - click the "Delete" button in the header
    await user.click(screen.getByRole('button', { name: /^delete$/i }));

    await waitFor(() => {
      expect(screen.getByText('Delete Project?')).toBeInTheDocument();
    });

    // Inside the modal, find the confirm delete button within the dialog
    const dialog = screen.getByRole('dialog');
    const confirmButton = within(dialog).getByRole('button', { name: /delete/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockApi.deleteProject).toHaveBeenCalledWith('project-1');
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to delete project',
          variant: 'destructive',
        }),
      );
    });
  });
});

describe('ProjectDetail - Remove Member', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('removes member successfully', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.removeMember.mockResolvedValue(undefined);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    const removeButtons = screen.getAllByRole('button', { name: /remove jane smith from team/i });
    await user.click(removeButtons[0]);

    await waitFor(() => {
      expect(mockApi.removeMember).toHaveBeenCalledWith('project-1', 'user-2');
      expect(mockToast).toHaveBeenCalledWith({ title: 'Member removed' });
    });
  });

  it('shows error toast when remove member fails', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.removeMember.mockRejectedValue(new Error('Remove failed'));

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    const removeButtons = screen.getAllByRole('button', { name: /remove jane smith from team/i });
    await user.click(removeButtons[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to remove member',
          variant: 'destructive',
        }),
      );
    });
  });
});

describe('ProjectDetail - Mobile Team Tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('opens profile dialog from mobile team tab member click', async () => {
    const user = userEvent.setup();
    mediaState.isDesktop = false;
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    // Mobile renders tabs; the team tab must be activated before its content mounts.
    const teamTab = await screen.findByRole('tab', { name: /team/i });
    await user.click(teamTab);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /view profile of jane smith/i }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /view profile of jane smith/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });
});

describe('ProjectDetail - Close Member Profile Dialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('closes profile dialog when dismissed', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    // Open the dialog
    const memberRow = screen.getAllByRole('button', { name: /view profile of jane smith/i })[0];
    await user.click(memberRow);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Close the dialog by pressing Escape
    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});

describe('ProjectDetail - Invite Modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('opens invite modal when Invite Experts button is clicked', async () => {
    const user = userEvent.setup();
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /invite experts/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /invite experts/i }));

    await waitFor(() => {
      // InviteExpertModal renders a dialog with invite-related content
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });
});

describe('ProjectDetail - Responsive single layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('mounts the opinion form once on desktop (no duplicated number inputs)', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save Opinion' })).toBeInTheDocument();
    });

    // One opinion form -> exactly one set of lower/peak/upper number inputs.
    // The old dual mount (desktop grid + mobile tabs together) rendered six.
    expect(screen.getAllByRole('spinbutton')).toHaveLength(3);
    expect(screen.getAllByRole('button', { name: 'Save Opinion' })).toHaveLength(1);
  });

  it('mounts the opinion form once on mobile (no duplicated number inputs)', async () => {
    mediaState.isDesktop = false;
    render(<ProjectDetail />);

    // Opinions is the default-active tab, so its form is the only one mounted.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save Opinion' })).toBeInTheDocument();
    });
    expect(screen.getAllByRole('spinbutton')).toHaveLength(3);
  });

  it('focuses the visible invalid field on submit instead of dropping focus to the body', async () => {
    const user = userEvent.setup();
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save Opinion' })).toBeInTheDocument();
    });

    // Singular getByLabelText also asserts each field exists exactly once.
    await user.type(screen.getByLabelText('Position'), 'Manager');
    await user.type(screen.getByLabelText(/lower/i), '60');
    await user.type(screen.getByLabelText(/peak/i), '40');
    await user.type(screen.getByLabelText(/upper/i), '80');

    const peakInput = screen.getByLabelText(/peak/i);
    await user.click(screen.getByRole('button', { name: 'Save Opinion' }));

    // The order violation (lower > peak) makes zod flag the peak field; the
    // single mounted copy is the visible one, so error focus lands on it
    // rather than on a hidden duplicate (which left activeElement on <body>).
    await waitFor(() => {
      expect(document.activeElement).toBe(peakInput);
    });
    expect(document.activeElement).not.toBe(document.body);
    expect(
      screen.getByText('Values must satisfy: lower ≤ peak ≤ upper'),
    ).toBeInTheDocument();
    expect(mockApi.createOrUpdateOpinion).not.toHaveBeenCalled();
  });
});

describe('ProjectDetail - Header Result Export', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('hides the export menu while there is no result yet', async () => {
    // defaultSetup() resolves getResult to null.
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument();
  });

  it('hides the export menu when a result exists but there are no opinions', async () => {
    mockApi.getOpinions.mockResolvedValue([]);
    mockApi.getResult.mockResolvedValue(createCalculationResult());

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /export/i })).not.toBeInTheDocument();
  });

  it('shows the export menu in the header once a result is available', async () => {
    mockApi.getOpinions.mockResolvedValue([createOpinion({ user_id: 'user-2' })]);
    mockApi.getResult.mockResolvedValue(createCalculationResult());

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
    });
  });

  it('exports a PDF from the header menu', async () => {
    const user = userEvent.setup();
    mockApi.getOpinions.mockResolvedValue([createOpinion({ user_id: 'user-2' })]);
    mockApi.getResult.mockResolvedValue(createCalculationResult());
    mockApi.exportProjectResult.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));

    render(<ProjectDetail />);

    const exportButton = await screen.findByRole('button', { name: /export/i });
    await user.click(exportButton);
    const pdfItem = await screen.findByRole('menuitem', { name: /pdf report/i });
    await user.click(pdfItem);

    await waitFor(() => {
      expect(mockApi.exportProjectResult).toHaveBeenCalledWith('project-1', 'pdf', 'en');
      expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'test-project-results.pdf');
    });
  });
});
