import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import Profile from '@/pages/Profile';
import { createUser } from '@tests/factories/user';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock api
const mockApi = {
  updateCurrentUser: vi.fn(),
  changePassword: vi.fn(),
  deleteAccount: vi.fn(),
  uploadPhoto: vi.fn(),
  deletePhoto: vi.fn(),
};
vi.mock('@/lib/api', () => ({
  api: {
    updateCurrentUser: (data: unknown) => mockApi.updateCurrentUser(data),
    changePassword: (data: unknown) => mockApi.changePassword(data),
    deleteAccount: () => mockApi.deleteAccount(),
    uploadPhoto: (file: File) => mockApi.uploadPhoto(file),
    deletePhoto: () => mockApi.deletePhoto(),
  },
}));

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// Mock useAuth
const mockUser = createUser({ first_name: 'John', last_name: 'Doe', email: 'john@example.com' });
const mockRefreshUser = vi.fn();
const mockLogout = vi.fn();

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    refreshUser: mockRefreshUser,
    logout: mockLogout,
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('Profile', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders user name and email', () => {
    render(<Profile />);

    // Name appears in both navbar and profile, use getAllByText
    const nameElements = screen.getAllByText('John Doe');
    expect(nameElements.length).toBeGreaterThan(0);
    expect(screen.getByText('john@example.com')).toBeInTheDocument();
  });

  it('renders user initials in avatar', () => {
    render(<Profile />);

    // JD appears in both navbar avatar and profile avatar
    const initials = screen.getAllByText('JD');
    expect(initials.length).toBeGreaterThanOrEqual(2);
  });

  it('renders Edit Profile section', () => {
    render(<Profile />);

    expect(screen.getByText('Edit Profile')).toBeInTheDocument();
    expect(screen.getByLabelText('First Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Last Name')).toBeInTheDocument();
  });

  it('renders Change Password section', () => {
    render(<Profile />);

    expect(screen.getByText('Change Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Current Password')).toBeInTheDocument();
    expect(screen.getByLabelText('New Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm New Password')).toBeInTheDocument();
  });

  it('renders Danger Zone section', () => {
    render(<Profile />);

    expect(screen.getByText('Danger Zone')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete Account' })).toBeInTheDocument();
  });

  it('pre-fills first name and last name inputs', () => {
    render(<Profile />);

    const firstNameInput = screen.getByLabelText('First Name') as HTMLInputElement;
    const lastNameInput = screen.getByLabelText('Last Name') as HTMLInputElement;

    expect(firstNameInput.value).toBe('John');
    expect(lastNameInput.value).toBe('Doe');
  });
});

describe('Profile - Edit Profile', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls api.updateCurrentUser on save', async () => {
    const user = userEvent.setup();
    mockApi.updateCurrentUser.mockResolvedValueOnce({});

    render(<Profile />);

    const firstNameInput = screen.getByLabelText('First Name');
    await user.clear(firstNameInput);
    await user.type(firstNameInput, 'Jane');

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(mockApi.updateCurrentUser).toHaveBeenCalledWith({
        first_name: 'Jane',
        last_name: 'Doe',
      });
    });
  });

  it('shows success toast on profile update', async () => {
    const user = userEvent.setup();
    mockApi.updateCurrentUser.mockResolvedValueOnce({});

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Profile updated' })
      );
    });
  });

  it('shows error for invalid name format', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    const firstNameInput = screen.getByLabelText('First Name');
    await user.clear(firstNameInput);
    await user.type(firstNameInput, 'John123');

    expect(screen.getByText(/can only contain letters/i)).toBeInTheDocument();
  });

  it('disables save button when first name is empty', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    const firstNameInput = screen.getByLabelText('First Name');
    await user.clear(firstNameInput);

    expect(screen.getByRole('button', { name: 'Save Changes' })).toBeDisabled();
  });
});

describe('Profile - Change Password', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls api.changePassword with correct data', async () => {
    const user = userEvent.setup();
    mockApi.changePassword.mockResolvedValueOnce({});

    render(<Profile />);

    await user.type(screen.getByLabelText('Current Password'), 'oldPassword123!');
    await user.type(screen.getByLabelText('New Password'), 'NewPassword1!@#');
    await user.type(screen.getByLabelText('Confirm New Password'), 'NewPassword1!@#');

    await user.click(screen.getByRole('button', { name: 'Update Password' }));

    await waitFor(() => {
      expect(mockApi.changePassword).toHaveBeenCalledWith({
        current_password: 'oldPassword123!',
        new_password: 'NewPassword1!@#',
      });
    });
  });

  it('shows error toast when passwords do not match', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    await user.type(screen.getByLabelText('Current Password'), 'oldPassword123!');
    await user.type(screen.getByLabelText('New Password'), 'NewPassword1!@#');
    await user.type(screen.getByLabelText('Confirm New Password'), 'DiffPassword1!@#');

    await user.click(screen.getByRole('button', { name: 'Update Password' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          variant: 'destructive',
          description: 'Passwords do not match',
        })
      );
    });
  });

  it('shows password requirements when typing new password', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    await user.type(screen.getByLabelText('New Password'), 'abc');

    expect(screen.getByText(/at least 12 characters/i)).toBeInTheDocument();
  });

  it('disables update button when fields are empty', () => {
    render(<Profile />);

    expect(screen.getByRole('button', { name: 'Update Password' })).toBeDisabled();
  });
});

describe('Profile - Photo Buttons a11y', () => {
  const originalPhotoUrl = mockUser.photo_url;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.photo_url = null;
  });

  afterEach(() => {
    mockUser.photo_url = originalPhotoUrl;
  });

  it('upload photo button has aria-label', () => {
    render(<Profile />);

    expect(screen.getByRole('button', { name: /upload photo|nahrát fotku/i })).toBeInTheDocument();
  });

  it('delete photo button has aria-label when photo exists', () => {
    mockUser.photo_url = 'https://example.com/photo.jpg';
    render(<Profile />);

    expect(screen.getByRole('button', { name: /delete photo|smazat fotku/i })).toBeInTheDocument();
  });
});

describe('Profile - Delete Account', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens delete confirmation modal', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    await user.click(screen.getByRole('button', { name: 'Delete Account' }));

    await waitFor(() => {
      expect(screen.getByText('Delete Account?')).toBeInTheDocument();
    });
  });

  it('calls api.deleteAccount and navigates to home on confirm', async () => {
    const user = userEvent.setup();
    mockApi.deleteAccount.mockResolvedValueOnce({});

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: 'Delete Account' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Delete My Account' }));

    await waitFor(() => {
      expect(mockApi.deleteAccount).toHaveBeenCalled();
      expect(mockLogout).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('shows error toast when deleteAccount fails', async () => {
    const user = userEvent.setup();
    mockApi.deleteAccount.mockRejectedValueOnce(new Error('Server error'));

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: 'Delete Account' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Delete My Account' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Server error',
          variant: 'destructive',
        })
      );
    });
  });

  it('shows fallback error toast when deleteAccount throws non-Error', async () => {
    const user = userEvent.setup();
    mockApi.deleteAccount.mockRejectedValueOnce('unknown');

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: 'Delete Account' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Delete My Account' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to delete account',
          variant: 'destructive',
        })
      );
    });
  });
});

describe('Profile - Photo Upload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows error toast when file exceeds 5 MB', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    const fileInput = screen.getByLabelText('Profile photo') as HTMLInputElement;
    const oversizedFile = new File(['x'.repeat(6 * 1024 * 1024)], 'big.png', { type: 'image/png' });
    Object.defineProperty(oversizedFile, 'size', { value: 6 * 1024 * 1024 });

    await user.upload(fileInput, oversizedFile);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'File too large. Maximum size is 5 MB',
          variant: 'destructive',
        })
      );
    });
    expect(mockApi.uploadPhoto).not.toHaveBeenCalled();
  });

  it('uploads photo successfully and shows success toast', async () => {
    const user = userEvent.setup();
    mockApi.uploadPhoto.mockResolvedValueOnce({});
    mockRefreshUser.mockResolvedValueOnce(undefined);

    render(<Profile />);

    const fileInput = screen.getByLabelText('Profile photo') as HTMLInputElement;
    const validFile = new File(['photo-data'], 'avatar.png', { type: 'image/png' });

    await user.upload(fileInput, validFile);

    await waitFor(() => {
      expect(mockApi.uploadPhoto).toHaveBeenCalledWith(validFile);
      expect(mockRefreshUser).toHaveBeenCalled();
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Profile photo updated' })
      );
    });
  });

  it('shows error toast when upload API fails with Error', async () => {
    const user = userEvent.setup();
    mockApi.uploadPhoto.mockRejectedValueOnce(new Error('Upload failed'));

    render(<Profile />);

    const fileInput = screen.getByLabelText('Profile photo') as HTMLInputElement;
    const validFile = new File(['data'], 'pic.png', { type: 'image/png' });

    await user.upload(fileInput, validFile);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Upload failed',
          variant: 'destructive',
        })
      );
    });
  });

  it('shows fallback error toast when upload throws non-Error', async () => {
    const user = userEvent.setup();
    mockApi.uploadPhoto.mockRejectedValueOnce('unknown');

    render(<Profile />);

    const fileInput = screen.getByLabelText('Profile photo') as HTMLInputElement;
    const validFile = new File(['data'], 'pic.png', { type: 'image/png' });

    await user.upload(fileInput, validFile);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to upload photo',
          variant: 'destructive',
        })
      );
    });
  });

  it('triggers file input click when upload button is clicked', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    const fileInput = screen.getByLabelText('Profile photo') as HTMLInputElement;
    const clickSpy = vi.spyOn(fileInput, 'click');

    await user.click(screen.getByRole('button', { name: /upload photo/i }));

    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });
});

describe('Profile - Photo Delete', () => {
  const originalPhotoUrl = mockUser.photo_url;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUser.photo_url = 'https://example.com/photo.jpg';
  });

  afterEach(() => {
    mockUser.photo_url = originalPhotoUrl;
  });

  it('deletes photo successfully and shows success toast', async () => {
    const user = userEvent.setup();
    mockApi.deletePhoto.mockResolvedValueOnce({});
    mockRefreshUser.mockResolvedValueOnce(undefined);

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: /delete photo/i }));

    await waitFor(() => {
      expect(mockApi.deletePhoto).toHaveBeenCalled();
      expect(mockRefreshUser).toHaveBeenCalled();
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Profile photo removed' })
      );
    });
  });

  it('shows error toast when delete photo fails', async () => {
    const user = userEvent.setup();
    mockApi.deletePhoto.mockRejectedValueOnce(new Error('Delete failed'));

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: /delete photo/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to remove photo',
          variant: 'destructive',
        })
      );
    });
  });
});

describe('Profile - Name Validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows error for invalid first name then clears on valid input', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    const firstNameInput = screen.getByLabelText('First Name');
    await user.clear(firstNameInput);
    await user.type(firstNameInput, 'John123');

    expect(screen.getByText(/can only contain letters/i)).toBeInTheDocument();
    expect(firstNameInput).toHaveAttribute('aria-invalid', 'true');

    await user.clear(firstNameInput);
    await user.type(firstNameInput, 'John');

    expect(screen.queryByText(/can only contain letters/i)).not.toBeInTheDocument();
    expect(firstNameInput).toHaveAttribute('aria-invalid', 'false');
  });

  it('shows error for invalid last name then clears on valid input', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    const lastNameInput = screen.getByLabelText('Last Name');
    await user.clear(lastNameInput);
    await user.type(lastNameInput, 'Doe@!');

    const alerts = screen.getAllByRole('alert');
    expect(alerts.length).toBeGreaterThan(0);

    await user.clear(lastNameInput);
    await user.type(lastNameInput, 'Doe');

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('disables save button when name has validation errors', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    const firstNameInput = screen.getByLabelText('First Name');
    await user.clear(firstNameInput);
    await user.type(firstNameInput, 'Invalid123');

    expect(screen.getByRole('button', { name: 'Save Changes' })).toBeDisabled();
  });
});

describe('Profile - Password Change Success/Error', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows success toast and clears fields on successful password change', async () => {
    const user = userEvent.setup();
    mockApi.changePassword.mockResolvedValueOnce({});

    render(<Profile />);

    await user.type(screen.getByLabelText('Current Password'), 'OldPassword1!@#');
    await user.type(screen.getByLabelText('New Password'), 'NewPassword1!@#');
    await user.type(screen.getByLabelText('Confirm New Password'), 'NewPassword1!@#');

    await user.click(screen.getByRole('button', { name: 'Update Password' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Password updated' })
      );
    });

    // Fields should be cleared
    await waitFor(() => {
      expect((screen.getByLabelText('Current Password') as HTMLInputElement).value).toBe('');
      expect((screen.getByLabelText('New Password') as HTMLInputElement).value).toBe('');
      expect((screen.getByLabelText('Confirm New Password') as HTMLInputElement).value).toBe('');
    });
  });

  it('shows error toast when password change API fails with Error', async () => {
    const user = userEvent.setup();
    mockApi.changePassword.mockRejectedValueOnce(new Error('Wrong password'));

    render(<Profile />);

    await user.type(screen.getByLabelText('Current Password'), 'OldPassword1!@#');
    await user.type(screen.getByLabelText('New Password'), 'NewPassword1!@#');
    await user.type(screen.getByLabelText('Confirm New Password'), 'NewPassword1!@#');

    await user.click(screen.getByRole('button', { name: 'Update Password' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Wrong password',
          variant: 'destructive',
        })
      );
    });
  });

  it('shows fallback error toast when password change throws non-Error', async () => {
    const user = userEvent.setup();
    mockApi.changePassword.mockRejectedValueOnce('unknown');

    render(<Profile />);

    await user.type(screen.getByLabelText('Current Password'), 'OldPassword1!@#');
    await user.type(screen.getByLabelText('New Password'), 'NewPassword1!@#');
    await user.type(screen.getByLabelText('Confirm New Password'), 'NewPassword1!@#');

    await user.click(screen.getByRole('button', { name: 'Update Password' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to change password',
          variant: 'destructive',
        })
      );
    });
  });

  it('shows error toast when password requirements are not met', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    // Type weak password that doesn't meet all requirements
    await user.type(screen.getByLabelText('Current Password'), 'old');
    await user.type(screen.getByLabelText('New Password'), 'weak');
    await user.type(screen.getByLabelText('Confirm New Password'), 'weak');

    // Button should be disabled because requirements aren't met
    expect(screen.getByRole('button', { name: 'Update Password' })).toBeDisabled();
  });

  it('shows error toast when passwords do not match but requirements met', async () => {
    const user = userEvent.setup();
    render(<Profile />);

    await user.type(screen.getByLabelText('Current Password'), 'OldPassword1!@#');
    await user.type(screen.getByLabelText('New Password'), 'NewPassword1!@#');
    await user.type(screen.getByLabelText('Confirm New Password'), 'DiffPassword1!@#');

    // Both meet requirements so button should be clickable
    await user.click(screen.getByRole('button', { name: 'Update Password' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          description: 'Passwords do not match',
          variant: 'destructive',
        })
      );
    });
  });
});

describe('Profile - Profile Update Error', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows error toast when profile update fails with Error', async () => {
    const user = userEvent.setup();
    mockApi.updateCurrentUser.mockRejectedValueOnce(new Error('Network error'));

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Network error',
          variant: 'destructive',
        })
      );
    });
  });

  it('shows fallback error toast when profile update throws non-Error', async () => {
    const user = userEvent.setup();
    mockApi.updateCurrentUser.mockRejectedValueOnce('unknown');

    render(<Profile />);

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to update profile',
          variant: 'destructive',
        })
      );
    });
  });
});
