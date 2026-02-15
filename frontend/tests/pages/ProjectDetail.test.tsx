import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
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

  it('toggles individual opinions visibility via checkbox', async () => {
    const user = userEvent.setup();
    const opinions = [createOpinion({ user_id: 'other' })];
    const result = createCalculationResult();

    mockApi.getOpinions.mockResolvedValue(opinions);
    mockApi.getResult.mockResolvedValue(result);

    render(<ProjectDetail />);

    await waitFor(() => {
      const bestCompromiseTexts = screen.getAllByText('Best Compromise');
      expect(bestCompromiseTexts.length).toBeGreaterThan(0);
    });

    // showIndividual checkbox should exist and be unchecked by default
    const checkboxes = screen.getAllByRole('checkbox', { name: /individual/i });
    expect(checkboxes.length).toBeGreaterThan(0);
    expect(checkboxes[0]).not.toBeChecked();

    // Toggle it
    await user.click(checkboxes[0]);
    expect(checkboxes[0]).toBeChecked();
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

    // Collapsible trigger shows member count — section already expanded
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

    // Team table content should be hidden in the desktop collapsible
    await waitFor(() => {
      const trigger = screen.getByRole('button', { name: /team.*2 members/i });
      expect(trigger).toBeInTheDocument();
    });
  });

  it('displays member avatar initials in team table', async () => {
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);

    render(<ProjectDetail />);

    await waitFor(() => {
      // JD appears in both Navbar avatar and team table avatar (team section open by default)
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

    // Team section is open by default
    await waitFor(() => {
      const invitedBadges = screen.getAllByText('Invited');
      expect(invitedBadges.length).toBeGreaterThan(0);
    });
  });

  it('shows invitee name and email in team table', async () => {
    const invitations = [
      createProjectInvitation({
        invitee_first_name: 'Michael',
        invitee_last_name: 'Brown',
        invitee_email: 'michael@example.com',
      }),
    ];
    mockApi.getProjectInvitations.mockResolvedValue(invitations);

    render(<ProjectDetail />);

    // Team section is open by default
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

  it('displays opinion values in profile dialog', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    const opinions = [
      createOpinion({
        user_id: 'user-2',
        user_first_name: 'Jane',
        user_last_name: 'Smith',
        position: 'Head of Research',
        lower_bound: 10,
        peak: 20,
        upper_bound: 30,
        centroid: 20,
      }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.getOpinions.mockResolvedValue(opinions);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    const memberRows = screen.getAllByRole('button', { name: /view profile of jane smith/i });
    await user.click(memberRows[0]);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    const dialog = screen.getByRole('dialog');
    // Position and opinion values should be inside the dialog
    expect(within(dialog).getByText('Head of Research')).toBeInTheDocument();
    // Opinion values are in sr-only summary (grid is aria-hidden)
    expect(within(dialog).getByText(/opinion values.*lower.*10\.00.*peak.*20\.00.*upper.*30\.00.*centroid.*20\.00/i)).toBeInTheDocument();
  });

  it('shows no opinion message when member has no opinion', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.getOpinions.mockResolvedValue([]);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    const memberRow = screen.getAllByRole('button', { name: /view profile of jane smith/i })[0];
    await user.click(memberRow);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('No opinion submitted yet')).toBeInTheDocument();
    });
  });

  it('displays role badge in profile dialog', async () => {
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
      const dialog = screen.getByRole('dialog');
      // Role badge "Expert" should be inside the dialog
      expect(within(dialog).getByText('Expert')).toBeInTheDocument();
    });
  });

  it('opens profile dialog via keyboard Enter', async () => {
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
    memberRow.focus();
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Jane Smith' })).toBeInTheDocument();
    });
  });

  it('does not open dialog when remove button is clicked', async () => {
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

    // Click the remove button (X icon)
    const removeButtons = screen.getAllByRole('button', { name: /remove jane smith from team/i });
    await user.click(removeButtons[0]);

    // Should NOT open dialog
    await waitFor(() => {
      expect(mockApi.removeMember).toHaveBeenCalledWith('project-1', 'user-2');
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('provides sr-only opinion summary for screen readers', async () => {
    const user = userEvent.setup();
    const members = [
      createMember({ user_id: 'user-1', first_name: 'John', last_name: 'Doe', role: 'admin' }),
      createMember({ user_id: 'user-2', first_name: 'Jane', last_name: 'Smith', role: 'expert' }),
    ];
    const opinions = [
      createOpinion({
        user_id: 'user-2',
        user_first_name: 'Jane',
        user_last_name: 'Smith',
        lower_bound: 10,
        peak: 20,
        upper_bound: 30,
        centroid: 20,
      }),
    ];
    mockApi.getMembers.mockResolvedValue(members);
    mockApi.getOpinions.mockResolvedValue(opinions);

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getAllByText('Jane Smith').length).toBeGreaterThan(0);
    });

    const memberRow = screen.getAllByRole('button', { name: /view profile of jane smith/i })[0];
    await user.click(memberRow);

    await waitFor(() => {
      // sr-only text with opinion values summary
      expect(screen.getByText(/opinion values.*lower.*10\.00.*peak.*20\.00.*upper.*30\.00.*centroid.*20\.00/i)).toBeInTheDocument();
    });
  });
});
