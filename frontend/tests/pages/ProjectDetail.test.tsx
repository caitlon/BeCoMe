import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import ProjectDetail from '@/pages/ProjectDetail';
import { createProject, createOpinion, createMember, createCalculationResult, createProjectInvitation } from '@tests/factories/project';

// Use vi.hoisted for mock variables
const { mockApi, mockToast, mockUser, mockNavigate } = vi.hoisted(() => ({
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
  },
  mockToast: vi.fn(),
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
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: 'project-1' }),
    useNavigate: () => mockNavigate,
  };
});

// Mock api
vi.mock('@/lib/api', () => ({
  api: mockApi,
}));

// Mock useToast
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock useAuth
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
  }),
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

const defaultSetup = () => {
  const project = createProject({
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
      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /invite experts/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
    });
  });

  it('hides admin buttons for expert users', async () => {
    mockApi.getProject.mockResolvedValue(createProject({ role: 'expert' }));

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
    });
  });

  it('renders back to projects link', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /projects/i })).toHaveAttribute('href', '/projects');
    });
  });
});

describe('ProjectDetail - Opinion Form', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('shows save button when no opinion exists', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      // Use getAllByRole because there might be multiple due to responsive layout
      const buttons = screen.getAllByRole('button', { name: 'Save Opinion' });
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('shows update button when user has existing opinion', async () => {
    const existingOpinion = createOpinion({
      user_id: 'user-1',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
      position: 'Manager',
    });
    mockApi.getOpinions.mockResolvedValue([existingOpinion]);

    render(<ProjectDetail />);

    await waitFor(() => {
      const buttons = screen.getAllByRole('button', { name: 'Update Opinion' });
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('shows delete opinion link when user has opinion', async () => {
    const existingOpinion = createOpinion({ user_id: 'user-1' });
    mockApi.getOpinions.mockResolvedValue([existingOpinion]);

    render(<ProjectDetail />);

    await waitFor(() => {
      const deleteLinks = screen.getAllByText('Delete my opinion');
      expect(deleteLinks.length).toBeGreaterThan(0);
    });
  });

  it('disables update button when opinion values unchanged', async () => {
    const existingOpinion = createOpinion({
      user_id: 'user-1',
      position: 'Manager',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
    });
    mockApi.getOpinions.mockResolvedValue([existingOpinion]);

    render(<ProjectDetail />);

    await waitFor(() => {
      const buttons = screen.getAllByRole('button', { name: 'Update Opinion' });
      expect(buttons[0]).toBeDisabled();
    });
  });

  it('disables save button when position is empty', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      const buttons = screen.getAllByRole('button', { name: 'Save Opinion' });
      expect(buttons[0]).toBeDisabled();
    });
  });
});

describe('ProjectDetail - Other Opinions Table', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('shows "no other opinions" when empty', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      const noOpinionsTexts = screen.getAllByText('No other opinions yet');
      expect(noOpinionsTexts.length).toBeGreaterThan(0);
    });
  });

  it('displays other expert opinions', async () => {
    const otherOpinions = [
      createOpinion({
        user_id: 'other-user',
        user_first_name: 'Jane',
        user_last_name: 'Smith',
        lower_bound: 30,
        peak: 60,
        upper_bound: 90,
      }),
    ];
    mockApi.getOpinions.mockResolvedValue(otherOpinions);

    render(<ProjectDetail />);

    await waitFor(() => {
      const names = screen.getAllByText('Jane Smith');
      expect(names.length).toBeGreaterThan(0);
    });
  });
});

describe('ProjectDetail - Results Section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('shows "no results" message when no opinions', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      const noResultsTexts = screen.getAllByText(/results will appear once experts submit/i);
      expect(noResultsTexts.length).toBeGreaterThan(0);
    });
  });

  it('displays calculation results when available', async () => {
    const opinions = [createOpinion({ user_id: 'other' })];
    const result = createCalculationResult();

    mockApi.getOpinions.mockResolvedValue(opinions);
    mockApi.getResult.mockResolvedValue(result);

    render(<ProjectDetail />);

    await waitFor(() => {
      const bestCompromiseTexts = screen.getAllByText('Best Compromise');
      expect(bestCompromiseTexts.length).toBeGreaterThan(0);
    });
  });

  it('shows agreement badge with results', async () => {
    // max_error=12.5, scale 0-100, errorPercent=12.5% → "High agreement"
    const opinions = [createOpinion({ user_id: 'other' })];
    const result = createCalculationResult({ max_error: 12.5 });

    mockApi.getOpinions.mockResolvedValue(opinions);
    mockApi.getResult.mockResolvedValue(result);

    render(<ProjectDetail />);

    await waitFor(() => {
      const badges = screen.getAllByText('High agreement');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it('shows moderate agreement for medium error', async () => {
    // max_error=30, scale 0-100, errorPercent=30% → "Moderate agreement"
    const opinions = [createOpinion({ user_id: 'other' })];
    const result = createCalculationResult({ max_error: 30 });

    mockApi.getOpinions.mockResolvedValue(opinions);
    mockApi.getResult.mockResolvedValue(result);

    render(<ProjectDetail />);

    await waitFor(() => {
      const badges = screen.getAllByText('Moderate agreement');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it('shows low agreement for high error', async () => {
    // max_error=50, scale 0-100, errorPercent=50% → "Low agreement"
    const opinions = [createOpinion({ user_id: 'other' })];
    const result = createCalculationResult({ max_error: 50 });

    mockApi.getOpinions.mockResolvedValue(opinions);
    mockApi.getResult.mockResolvedValue(result);

    render(<ProjectDetail />);

    await waitFor(() => {
      const badges = screen.getAllByText('Low agreement');
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it('renders visualization tabs (Triangle and Centroid)', async () => {
    const opinions = [createOpinion({ user_id: 'other' })];
    const result = createCalculationResult();

    mockApi.getOpinions.mockResolvedValue(opinions);
    mockApi.getResult.mockResolvedValue(result);

    render(<ProjectDetail />);

    await waitFor(() => {
      const triangleTabs = screen.getAllByRole('tab', { name: /triangle/i });
      expect(triangleTabs.length).toBeGreaterThan(0);
      const centroidTabs = screen.getAllByRole('tab', { name: /centroid/i });
      expect(centroidTabs.length).toBeGreaterThan(0);
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

  it('displays member avatar initials in team table', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /team.*1 members/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /team.*1 members/i }));

    await waitFor(() => {
      // JD appears in both Navbar avatar and team table avatar
      const initials = screen.getAllByText('JD');
      expect(initials.length).toBeGreaterThanOrEqual(2);
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

describe('ProjectDetail - Pending Members', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('shows awaiting response for members without opinions', async () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
      createMember({ user_id: 'user-3', first_name: 'Anna', last_name: 'Lee', role: 'expert' }),
    ];
    const opinions = [
      createOpinion({ user_id: 'user-2', user_first_name: 'Jane', user_last_name: 'Smith' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.getOpinions.mockResolvedValue(opinions);

    render(<ProjectDetail />);

    await waitFor(() => {
      // Anna has no opinion and is not the current user — should see "Awaiting response"
      const awaitingTexts = screen.getAllByText('Awaiting response');
      expect(awaitingTexts.length).toBeGreaterThan(0);
      // Verify Anna specifically appears as pending
      const annaTexts = screen.getAllByText('Anna Lee');
      expect(annaTexts.length).toBeGreaterThan(0);
    });
  });

  it('does not show current user as pending member', async () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    // No opinions at all — user-1 (current user) should NOT appear as pending
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.getOpinions.mockResolvedValue([]);

    render(<ProjectDetail />);

    await waitFor(() => {
      // Only Jane should be pending — current user (John) must be excluded.
      // Text appears twice: once in desktop layout, once in mobile tab.
      const awaitingTexts = screen.getAllByText('Awaiting response');
      expect(awaitingTexts).toHaveLength(2);
    });
  });

  it('shows table when only pending members exist (no opinions)', async () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.getOpinions.mockResolvedValue([]);

    render(<ProjectDetail />);

    await waitFor(() => {
      // Table should render (not "no other opinions" empty state)
      const awaitingTexts = screen.getAllByText('Awaiting response');
      expect(awaitingTexts.length).toBeGreaterThan(0);
    });
  });
});

describe('ProjectDetail - Pending Invitations in Team', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultSetup();
  });

  it('displays pending invitations in team table', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
    ];
    const invitations = [
      createProjectInvitation({
        invitee_first_name: 'Sophie',
        invitee_last_name: 'Wagner',
        invitee_email: 'sophie@example.com',
      }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.getProjectInvitations.mockResolvedValue(invitations);

    render(<ProjectDetail />);

    // Open the desktop collapsible to reveal the team table
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /team.*1 members/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /team.*1 members/i }));

    await waitFor(() => {
      const invitedBadges = screen.getAllByText('Invited');
      expect(invitedBadges.length).toBeGreaterThan(0);
    });
  });

  it('shows invitee name and email in team table', async () => {
    const user = userEvent.setup();
    const invitations = [
      createProjectInvitation({
        invitee_first_name: 'Michael',
        invitee_last_name: 'Brown',
        invitee_email: 'michael@example.com',
      }),
    ];
    mockApi.getProjectInvitations.mockResolvedValue(invitations);

    render(<ProjectDetail />);

    // Open the desktop collapsible
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /team.*0 members/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /team.*0 members/i }));

    await waitFor(() => {
      const names = screen.getAllByText('Michael Brown');
      expect(names.length).toBeGreaterThan(0);
      const emails = screen.getAllByText('michael@example.com');
      expect(emails.length).toBeGreaterThan(0);
    });
  });

  it('fetches project invitations on load', async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(mockApi.getProjectInvitations).toHaveBeenCalledWith('project-1');
    });
  });
});
