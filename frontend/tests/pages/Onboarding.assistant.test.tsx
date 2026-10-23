import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { framerMotionMock } from '@tests/utils';

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return { ...actual, useNavigate: () => vi.fn() };
});

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'john@example.com',
      first_name: 'John',
      last_name: 'Doe',
      photo_url: null,
      created_at: '2024-01-01T00:00:00Z',
    },
    isLoading: false,
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

// Counts how often the guide module is evaluated, can make that import fail the
// way a stale hashed chunk does after a deploy, and can hold it back until released.
const guide = vi.hoisted(() => ({
  loads: 0,
  fails: false,
  stepThrows: false,
  release: null as (() => void) | null,
  gate: null as Promise<void> | null,
}));

describe('Onboarding assistant step', () => {
  beforeEach(() => {
    // The assistant module computes its build flag once at module scope, so the
    // page and the helpers that share its i18n instance are re-imported per test.
    vi.resetModules();
    guide.loads = 0;
    guide.fails = false;
    guide.stepThrows = false;
    guide.release = null;
    guide.gate = null;
    // Registered per test, not hoisted: a hoisted factory runs once per file.
    vi.doMock('@/components/assistant/AssistantGuide', async (importOriginal) => {
      guide.loads += 1;
      if (guide.fails) throw new Error('chunk failed');
      if (guide.gate) await guide.gate;
      const original = await importOriginal<typeof import('@/components/assistant/AssistantGuide')>();
      if (!guide.stepThrows) return original;
      return {
        ...original,
        AssistantTourStep: () => {
          throw new Error('step failed');
        },
      };
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  async function renderOnboarding() {
    const { default: Onboarding } = await import('@/pages/Onboarding');
    const { render } = await import('@tests/utils');
    render(<Onboarding />, { initialEntries: ['/onboarding'] });
    return userEvent.setup();
  }

  async function next(user: ReturnType<typeof userEvent.setup>, times: number) {
    for (let i = 0; i < times; i++) {
      await user.click(screen.getByRole('button', { name: /get started|next|začít|další/i }));
    }
  }

  async function settle() {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
  }

  describe('in a build without the flag', () => {
    it('keeps six steps, goes from "view results" straight to "complete" and never imports the guide', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');
      const user = await renderOnboarding();

      expect(screen.getByText('Step 1 of 6')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: /go to step/i })).toHaveLength(6);

      await next(user, 5);
      await settle();

      expect(screen.getByText('Step 6 of 6')).toBeInTheDocument();
      expect(screen.queryByText('Ask the assistant')).not.toBeInTheDocument();
      expect(guide.loads).toBe(0);
    });
  });

  describe('in a build with the flag', () => {
    it('shows six steps on the first paint, then seven once the guide module has loaded', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      await renderOnboarding();

      expect(screen.getByText('Step 1 of 6')).toBeInTheDocument();
      expect(await screen.findByText('Step 1 of 7')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: /go to step/i })).toHaveLength(7);
      expect(guide.loads).toBe(1);
    });

    it('puts the assistant step right before "complete"', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      const user = await renderOnboarding();
      await screen.findByText('Step 1 of 7');

      await next(user, 5);
      expect(screen.getByText('Step 6 of 7')).toBeInTheDocument();
      expect(await screen.findByRole('heading', { name: 'Ask the assistant' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /documentation/i })).toHaveAttribute('href', '/docs');
      expect(screen.getByRole('link', { name: /documentation/i })).toHaveAttribute('target', '_blank');
      expect(screen.getByText(/opens in new tab/)).toHaveClass('sr-only');

      await next(user, 1);
      expect(screen.getByText('Step 7 of 7')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /go to projects/i })).toBeInTheDocument();
      expect(screen.queryByText('Ask the assistant')).not.toBeInTheDocument();
    });

    it('points to the header button with its icon instead of a label', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      const user = await renderOnboarding();
      await screen.findByText('Step 1 of 7');
      await next(user, 5);

      const body = await screen.findByText(/Click the assistant button/);
      expect(body.textContent).toBe(
        'Not sure what a result or a term means? Click the assistant button  in the top bar and ask in your own words. It knows the BeCoMe method and the projects you are a member of. It is an AI and can be wrong, so check what matters on the result page.',
      );
      expect(body.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    });

    it('speaks Czech when the language is Czech', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      const { default: i18n } = await import('@/i18n');
      await i18n.changeLanguage('cs');
      const user = await renderOnboarding();
      await screen.findByText('Krok 1 z 7');
      await next(user, 5);

      expect(await screen.findByRole('heading', { name: 'Zeptejte se asistenta' })).toBeInTheDocument();
      expect(screen.getByText(/Klikněte v horní liště na tlačítko asistenta/).querySelector('svg')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /dokumentaci/ })).toHaveAttribute('href', '/docs');
      await i18n.changeLanguage('en');
    });

    it('stays on "complete" when the step list grows under a user who already got there', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      guide.gate = new Promise<void>((resolve) => {
        guide.release = resolve;
      });
      const user = await renderOnboarding();

      await next(user, 5);
      expect(screen.getByText('Step 6 of 6')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /go to projects/i })).toBeInTheDocument();

      await act(async () => {
        guide.release?.();
      });

      expect(await screen.findByText('Step 7 of 7')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /go to projects/i })).toBeInTheDocument();
      expect(screen.queryByText('Ask the assistant')).not.toBeInTheDocument();
    });

    it('keeps the step the user is on when the list grows after the first paint', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      guide.gate = new Promise<void>((resolve) => {
        guide.release = resolve;
      });
      const user = await renderOnboarding();

      await next(user, 2);
      expect(screen.getByText('Step 3 of 6')).toBeInTheDocument();

      await act(async () => {
        guide.release?.();
      });

      expect(await screen.findByText('Step 3 of 7')).toBeInTheDocument();
    });

    it('keeps six steps when the module fails to load', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      guide.fails = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      const user = await renderOnboarding();
      await settle();

      expect(screen.getByText('Step 1 of 6')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: /go to step/i })).toHaveLength(6);
      await next(user, 5);
      expect(screen.getByText('Step 6 of 6')).toBeInTheDocument();
      expect(guide.loads).toBe(1);
      consoleError.mockRestore();
    });

    it('drops the step when it throws while rendering and lands on "complete"', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      guide.stepThrows = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      const user = await renderOnboarding();
      await screen.findByText('Step 1 of 7');

      await next(user, 5);
      await settle();

      expect(screen.getByText('Step 6 of 6')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: /go to step/i })).toHaveLength(6);
      expect(screen.getByRole('button', { name: /go to projects/i })).toBeInTheDocument();
      consoleError.mockRestore();
    });
  });
});
