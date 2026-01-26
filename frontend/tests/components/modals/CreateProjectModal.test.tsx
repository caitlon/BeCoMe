import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { CreateProjectModal } from '@/components/modals/CreateProjectModal';

// Mock api
const mockCreateProject = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    createProject: (data: unknown) => mockCreateProject(data),
  },
}));

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

describe('CreateProjectModal', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onSuccess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getNameInput = () => screen.getByPlaceholderText('Enter project name');
  const getUnitInput = () => screen.getByPlaceholderText(/%, points/i);
  const getSubmitButton = () => screen.getByRole('button', { name: 'Create Project' });

  it('renders form fields when open', () => {
    render(<CreateProjectModal {...defaultProps} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(getNameInput()).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Min')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Max')).toBeInTheDocument();
  });

  it('has default scale values', () => {
    render(<CreateProjectModal {...defaultProps} />);

    const minInput = screen.getByPlaceholderText('Min') as HTMLInputElement;
    const maxInput = screen.getByPlaceholderText('Max') as HTMLInputElement;

    expect(minInput.value).toBe('0');
    expect(maxInput.value).toBe('100');
  });

  it('shows validation error when name is empty', async () => {
    const user = userEvent.setup();
    render(<CreateProjectModal {...defaultProps} />);

    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });

  it('requires unit field to be filled', async () => {
    const user = userEvent.setup();
    render(<CreateProjectModal {...defaultProps} />);

    // Fill name but leave unit empty
    await user.type(getNameInput(), 'Test Project');
    await user.click(getSubmitButton());

    // API should not be called without unit
    await waitFor(() => {
      expect(mockCreateProject).not.toHaveBeenCalled();
    });
  });

  it('shows validation error when max is not greater than min', async () => {
    const user = userEvent.setup();
    render(<CreateProjectModal {...defaultProps} />);

    await user.type(getNameInput(), 'Test Project');

    const minInput = screen.getByPlaceholderText('Min');
    const maxInput = screen.getByPlaceholderText('Max');

    await user.clear(minInput);
    await user.type(minInput, '100');
    await user.clear(maxInput);
    await user.type(maxInput, '50');
    await user.type(getUnitInput(), '%');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/max.*greater.*min/i)).toBeInTheDocument();
    });
  });

  it('calls api.createProject on valid submission', async () => {
    const user = userEvent.setup();
    mockCreateProject.mockResolvedValueOnce({ id: '1', name: 'Test' });

    render(<CreateProjectModal {...defaultProps} />);

    await user.type(getNameInput(), 'New Project');
    await user.type(getUnitInput(), '%');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockCreateProject).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'New Project',
          scale_min: 0,
          scale_max: 100,
          scale_unit: '%',
        })
      );
    });
  });

  it('shows loading state during submission', async () => {
    const user = userEvent.setup();
    mockCreateProject.mockImplementation(() => new Promise(() => {}));

    render(<CreateProjectModal {...defaultProps} />);

    await user.type(getNameInput(), 'New Project');
    await user.type(getUnitInput(), '%');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/creating/i)).toBeInTheDocument();
    });
  });

  it('calls onSuccess and onOpenChange on successful creation', async () => {
    const user = userEvent.setup();
    mockCreateProject.mockResolvedValueOnce({ id: '1' });

    render(<CreateProjectModal {...defaultProps} />);

    await user.type(getNameInput(), 'New Project');
    await user.type(getUnitInput(), '%');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(defaultProps.onSuccess).toHaveBeenCalled();
      expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('shows error toast on API failure', async () => {
    const user = userEvent.setup();
    mockCreateProject.mockRejectedValueOnce(new Error('Server error'));

    render(<CreateProjectModal {...defaultProps} />);

    await user.type(getNameInput(), 'New Project');
    await user.type(getUnitInput(), '%');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
        })
      );
    });
  });

  it('cancel button closes modal', async () => {
    const user = userEvent.setup();
    render(<CreateProjectModal {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
  });
});
