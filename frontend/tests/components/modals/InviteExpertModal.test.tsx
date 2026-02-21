import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, act } from '@testing-library/react';
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

  it('does not call api when projectId is undefined', async () => {
    const user = userEvent.setup();
    render(
      <InviteExpertModal open={true} onOpenChange={vi.fn()} projectName="Test" />
    );

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockInviteExpert).not.toHaveBeenCalled();
    });
  });

  it('shows fallback error message for non-Error exceptions', async () => {
    const user = userEvent.setup();
    mockInviteExpert.mockRejectedValueOnce('network timeout');

    render(<InviteExpertModal {...defaultProps} />);

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
        })
      );
      const call = mockToast.mock.calls[0][0];
      expect(call.description).not.toBe('network timeout');
    });
  });

  it('calls onOpenChange(false) when clicking Done on success state', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    mockInviteExpert.mockResolvedValueOnce({});

    render(<InviteExpertModal {...defaultProps} onOpenChange={onOpenChange} />);

    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText('Invitation sent!')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /done/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('handleClose setTimeout resets success state and form after delay', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    mockInviteExpert.mockResolvedValueOnce({});

    const { rerender } = render(
      <InviteExpertModal {...defaultProps} onOpenChange={onOpenChange} />
    );

    // Submit to reach success state
    await user.type(getEmailInput(), 'expert@test.com');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText('Invitation sent!')).toBeInTheDocument();
    });

    // Click Done — triggers handleClose with setTimeout(200ms)
    await user.click(screen.getByRole('button', { name: /done/i }));

    // Wait for the setTimeout(200ms) callback to fire
    await act(async () => {
      await new Promise((r) => setTimeout(r, 250));
    });

    // Rerender with open=true — form should show (not success state)
    rerender(<InviteExpertModal {...defaultProps} open={true} onOpenChange={onOpenChange} />);

    expect(screen.getByPlaceholderText('expert@example.com')).toBeInTheDocument();
  });
});
