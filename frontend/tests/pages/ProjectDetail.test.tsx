import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import ProjectDetail from '@/pages/ProjectDetail';
import { createProject, createOpinion, createMember, createCalculationResult } from '@tests/factories/project';

// Use vi.hoisted for mock variables
const { mockApi, mockToast, mockUser, mockNavigate } = vi.hoisted(() => ({
  mockApi: {
    getProject: vi.fn(),
    getOpinions: vi.fn(),
    getResult: vi.fn(),
    getMembers: vi.fn(),
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

    render(<ProjectDetail />);

    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
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
      expect(screen.getByText(/team.*2 members/i)).toBeInTheDocument();
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
