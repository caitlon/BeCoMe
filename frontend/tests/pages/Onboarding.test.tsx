import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import Onboarding from '@/pages/Onboarding';

const { mockUser, mockNavigate, mockPathname } = vi.hoisted(() => ({
  mockUser: {
    id: 'user-1',
    email: 'john@example.com',
    first_name: 'John',
    last_name: 'Doe',
    photo_url: null,
    created_at: '2024-01-01T00:00:00Z',
  },
  mockNavigate: vi.fn(),
  mockPathname: { value: '/onboarding' },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ pathname: mockPathname.value, search: '', hash: '', state: null, key: 'default' }),
  };
});

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Onboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.value = '/onboarding';
  });

  it('renders first step (Welcome) on load', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    expect(screen.getByText('Welcome to BeCoMe')).toBeInTheDocument();
  });

  it('Previous button is disabled on step 1', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const prevButton = screen.getByRole('button', { name: /previous/i });
    expect(prevButton).toBeDisabled();
  });

  it('Next button advances to step 2', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const nextButton = screen.getByRole('button', { name: /get started/i });
    await user.click(nextButton);

    expect(screen.getByText('Create a Project')).toBeInTheDocument();
  });

  it('Previous button goes back from step 2 to step 1', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Go to step 2
    await user.click(screen.getByRole('button', { name: /get started/i }));
    expect(screen.getByText('Create a Project')).toBeInTheDocument();

    // Go back
    await user.click(screen.getByRole('button', { name: /previous/i }));
    expect(screen.getByText('Welcome to BeCoMe')).toBeInTheDocument();
  });

  it('clicking step dot navigates to that step', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Click step dot 3 (Go to step 3)
    const stepDot3 = screen.getByRole('button', { name: /go to step 3/i });
    await user.click(stepDot3);

    expect(screen.getByText('Invite Experts')).toBeInTheDocument();
  });

  it('last step shows Finish instead of Next', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Navigate to last step (step 6) via step dots
    const lastStepDot = screen.getByRole('button', { name: /go to step 6/i });
    await user.click(lastStepDot);

    expect(screen.getByRole('button', { name: /go to projects/i })).toBeInTheDocument();
  });

  it('Finish navigates to /projects', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Go to last step
    await user.click(screen.getByRole('button', { name: /go to step 6/i }));

    // Click Finish
    await user.click(screen.getByRole('button', { name: /go to projects/i }));

    expect(mockNavigate).toHaveBeenCalledWith('/projects');
  });

  it('Skip navigates to /projects', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    const skipButton = screen.getByRole('button', { name: /skip/i });
    await user.click(skipButton);

    expect(mockNavigate).toHaveBeenCalledWith('/projects');
  });

  it('progress bar increases per step', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Step 1 of 6 → ~16.7%
    expect(screen.getByText(/step 1 of 6/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /get started/i }));

    // Step 2 of 6
    expect(screen.getByText(/step 2 of 6/i)).toBeInTheDocument();
  });

  it('step counter label updates', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    expect(screen.getByText(/step 1 of 6/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /go to step 4/i }));

    expect(screen.getByText(/step 4 of 6/i)).toBeInTheDocument();
  });

  it('renders progress bar element', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('renders Skip button', () => {
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    expect(screen.getByRole('button', { name: /skip/i })).toBeInTheDocument();
  });
});

describe('Onboarding - Keyboard Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.value = '/onboarding';
  });

  it('ArrowRight advances to next step', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    expect(screen.getByText('Welcome to BeCoMe')).toBeInTheDocument();

    await user.keyboard('{ArrowRight}');

    expect(screen.getByText('Create a Project')).toBeInTheDocument();
  });

  it('ArrowLeft goes to previous step', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Go to step 2 first
    await user.click(screen.getByRole('button', { name: /get started/i }));
    expect(screen.getByText('Create a Project')).toBeInTheDocument();

    await user.keyboard('{ArrowLeft}');

    expect(screen.getByText('Welcome to BeCoMe')).toBeInTheDocument();
  });

  it('ArrowLeft does nothing on first step', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    await user.keyboard('{ArrowLeft}');

    // Still on step 1
    expect(screen.getByText('Welcome to BeCoMe')).toBeInTheDocument();
  });

  it('ArrowRight does nothing on last step', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Go to last step
    await user.click(screen.getByRole('button', { name: /go to step 6/i }));

    await user.keyboard('{ArrowRight}');

    // Still on last step
    expect(screen.getByRole('button', { name: /go to projects/i })).toBeInTheDocument();
  });

  it('Escape navigates to /projects', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    await user.keyboard('{Escape}');

    expect(mockNavigate).toHaveBeenCalledWith('/projects');
  });

  it('keyboard events are ignored when focus is in an input', async () => {
    const user = userEvent.setup();
    render(<Onboarding />, { initialEntries: ['/onboarding'] });

    // Go to step 2 (StepCreateProject has inputs)
    await user.click(screen.getByRole('button', { name: /get started/i }));
    expect(screen.getByText('Create a Project')).toBeInTheDocument();

    // Focus an input and press ArrowRight
    const inputs = screen.getAllByRole('textbox');
    await user.click(inputs[0]);
    await user.keyboard('{ArrowRight}');

    // Should still be on step 2 (keyboard nav skipped)
    expect(screen.getByText('Create a Project')).toBeInTheDocument();
  });
});
