import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import VerifyEmail from '@/pages/VerifyEmail';
import { ForbiddenError, HttpError, RateLimitError, ServerError } from '@/lib/errors';
import i18n from '@/i18n';

// Mock the API client (the page calls api.verifyEmail directly)
const mockVerifyEmail = vi.fn();
const mockResendVerification = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    verifyEmail: (token: string, password: string, language: string) =>
      mockVerifyEmail(token, password, language),
    resendVerification: (email: string, password: string) =>
      mockResendVerification(email, password),
  },
}));

// Mock navigation only; the token itself comes from a real query string via
// createWrapper's initialEntries below, exercising the real useSearchParams.
const mockNavigate = vi.fn();
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock useToast
const mockToast = vi.fn();
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// AuthLayout renders Navbar, which calls useAuth -> mock it (as the other auth
// page tests do).
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

const VALID_TOKEN = 'valid-verify-token';

// Starts the page at a specific route, so useSearchParams reads a real query
// string (createWrapper(initialEntries), per the test conventions this page's
// tests need).
const renderAt = (token: string | null = VALID_TOKEN) =>
  render(<VerifyEmail />, {
    initialEntries: [token ? `/verify-email?token=${token}` : '/verify-email'],
  });

describe('VerifyEmail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getPasswordInput = () => screen.getByPlaceholderText('Enter your password');
  const getSubmitButton = () => screen.getByRole('button', { name: /confirm email/i });
  // Navbar always renders its own "Sign In" nav link, so a plain getByRole
  // would find two matches; filter down to the page's own link by href.
  const getLoginLink = () =>
    screen
      .getAllByRole('link', { name: /sign in/i })
      .find((link) => link.getAttribute('href') === '/login');
  // The two locale-switching tests below render the page in whatever language
  // they set, so the English-text lookups above (placeholder, button name)
  // cannot find anything once the UI genuinely renders in Czech. The DOM
  // attributes react-hook-form and SubmitButton set are not translated, so
  // they work regardless of which language is active.
  const getPasswordInputByAttribute = (container: HTMLElement) =>
    container.querySelector<HTMLInputElement>('input[name="password"]');
  const getSubmitButtonByAttribute = (container: HTMLElement) =>
    container.querySelector<HTMLButtonElement>('button[type="submit"]');

  it('renders the password field and submit button when a token is present', () => {
    renderAt();

    expect(getPasswordInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
  });

  it('does not call api.verifyEmail on mount', async () => {
    renderAt();

    // Flush a tick so a stray effect-driven auto-submit would have fired.
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockVerifyEmail).not.toHaveBeenCalled();
  });

  it('shows a missing-link message instead of a form when the token is absent', () => {
    renderAt(null);

    expect(screen.queryByPlaceholderText('Enter your password')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /confirm email/i })).not.toBeInTheDocument();
    expect(getLoginLink()).toBeInTheDocument();
  });

  it('shows a loading state during submission', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockImplementation(() => new Promise(() => {}));
    renderAt();

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByText(/confirming/i)).toBeInTheDocument();
    });
  });

  it('calls api.verifyEmail with the token and password, then navigates to /login on success', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockResolvedValueOnce(undefined);
    renderAt();

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockVerifyEmail).toHaveBeenCalledWith(VALID_TOKEN, 'CorrectHorse123!', 'en');
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: expect.any(String) })
    );
  });

  it('sends the active UI language so the example project is seeded in it', async () => {
    const user = userEvent.setup();
    renderAt();

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockVerifyEmail).toHaveBeenCalledWith(VALID_TOKEN, 'CorrectHorse123!', 'en');
    });
  });

  // The activation link is opened straight from an email, so the browser's
  // language is whatever the visitor's OS or browser reports, entirely outside
  // our control. i18next has no supportedLngs allowlist, so i18n.language
  // resolves to that raw value (e.g. "de-DE") rather than being clamped to a
  // language we actually have resources for. The backend only accepts "en"
  // or "cs" (Literal["en", "cs"]), so an unclamped third language 422s the
  // request and silently breaks activation for that visitor.
  it('sends "en" to the backend when the browser language is neither English nor Czech', async () => {
    const user = userEvent.setup();
    await i18n.changeLanguage('de-DE');
    try {
      const { container } = renderAt();

      await user.type(getPasswordInputByAttribute(container)!, 'CorrectHorse123!');
      await user.click(getSubmitButtonByAttribute(container)!);

      await waitFor(() => {
        expect(mockVerifyEmail).toHaveBeenCalledWith(VALID_TOKEN, 'CorrectHorse123!', 'en');
      });
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('still sends "cs" to the backend when the browser language is Czech', async () => {
    const user = userEvent.setup();
    await i18n.changeLanguage('cs-CZ');
    try {
      const { container } = renderAt();

      await user.type(getPasswordInputByAttribute(container)!, 'CorrectHorse123!');
      await user.click(getSubmitButtonByAttribute(container)!);

      await waitFor(() => {
        expect(mockVerifyEmail).toHaveBeenCalledWith(VALID_TOKEN, 'CorrectHorse123!', 'cs');
      });
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('keeps the form and token in place on a 403 (wrong password), without navigating away', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new ForbiddenError());
    renderAt();

    await user.type(getPasswordInput(), 'WrongPassword123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/password/i);
    });

    expect(getPasswordInput()).toBeInTheDocument();
    expect(getSubmitButton()).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('replaces the form with a login link on a 400 (unusable link)', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new HttpError('Invalid or expired token', 400));
    renderAt();

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.queryByPlaceholderText('Enter your password')).not.toBeInTheDocument();
    });

    expect(getLoginLink()).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows a distinct locked-out message on a 429, without navigating away', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new RateLimitError());
    renderAt();

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/too many attempts/i);
    });

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('lets a locked-out attempt be retried, which is what the message tells the user to do', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new RateLimitError());
    renderAt();

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(getSubmitButton()).toBeEnabled();

    // The lockout lifts on its own, so the same form and the same link must be able
    // to carry the next attempt without a page reload.
    mockVerifyEmail.mockResolvedValueOnce(undefined);
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a generic error toast for an unexpected failure (e.g. service unavailable)', async () => {
    const user = userEvent.setup();
    mockVerifyEmail.mockRejectedValueOnce(new ServerError());
    renderAt();

    await user.type(getPasswordInput(), 'CorrectHorse123!');
    await user.click(getSubmitButton());

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ variant: 'destructive' })
      );
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
