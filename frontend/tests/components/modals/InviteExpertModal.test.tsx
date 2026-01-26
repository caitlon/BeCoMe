import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { InviteExpertModal } from '@/components/modals/InviteExpertModal';

// Mock api
const mockInviteExpert = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    inviteExpert: (projectId: string, email: string) => mockInviteExpert(projectId, email),
  },
}));

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

describe('InviteExpertModal', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    projectId: 'project-123',
    projectName: 'Test Research Project',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getEmailInput = () => screen.getByPlaceholderText('expert@example.com');
  const getSubmitButton = () => screen.getByRole('button', { name: 'Send Invitation' });

  it('renders project name in modal', () => {
    render(<InviteExpertModal {...defaultProps} />);

    expect(screen.getByText('Test Research Project')).toBeInTheDocument();
  });

  it('renders email input field', () => {
    render(<InviteExpertModal {...defaultProps} />);

    expect(getEmailInput()).toBeInTheDocument();
  });

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup();
    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'invalid-email');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByText(/invalid.*email/i)).toBeInTheDocument();
    });
  });

  it('shows loading state during submission', async () => {
    const user = userEvent.setup();
    mockInviteExpert.mockImplementation(() => new Promise(() => {}));

    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/sending/i)).toBeInTheDocument();
    });
  });

  it('calls api.inviteExpert with correct params', async () => {
    const user = userEvent.setup();
    mockInviteExpert.mockResolvedValueOnce({});

    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'newexpert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockInviteExpert).toHaveBeenCalledWith('project-123', 'newexpert@test.com');
    });
  });

  it('shows success state after successful invite', async () => {
    const user = userEvent.setup();
    mockInviteExpert.mockResolvedValueOnce({});

    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText('Invitation sent!')).toBeInTheDocument();
    });
  });

  it('shows invite another button on success', async () => {
    const user = userEvent.setup();
    mockInviteExpert.mockResolvedValueOnce({});

    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /invite another/i })).toBeInTheDocument();
    });
  });

  it('invite another resets form to input state', async () => {
    const user = userEvent.setup();
    mockInviteExpert.mockResolvedValueOnce({});

    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /invite another/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /invite another/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('expert@example.com')).toBeInTheDocument();
    });
  });

  it('shows error toast on API failure', async () => {
    const user = userEvent.setup();
    mockInviteExpert.mockRejectedValueOnce(new Error('User already invited'));

    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          description: 'User already invited',
        })
      );
    });
  });
});
