import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, screen, within } from '@testing-library/react';
import { framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);

vi.mock('framer-motion', () => framerMotionMock);

// Counts how often the guide module is evaluated, and can make that import fail
// the way a stale hashed chunk does after a deploy.
const guide = vi.hoisted(() => ({ loads: 0, fails: false, sectionThrows: false }));

describe('Documentation assistant section', () => {
  beforeEach(() => {
    // The assistant module computes its build flag once at module scope, so the
    // page and the helpers that share its i18n instance are re-imported per test.
    vi.resetModules();
    guide.loads = 0;
    guide.fails = false;
    guide.sectionThrows = false;
    // Registered per test, not hoisted: a hoisted factory runs once per file.
    vi.doMock('@/components/assistant/AssistantGuide', async (importOriginal) => {
      guide.loads += 1;
      if (guide.fails) throw new Error('chunk failed');
      const original = await importOriginal<typeof import('@/components/assistant/AssistantGuide')>();
      if (!guide.sectionThrows) return original;
      return {
        ...original,
        AssistantDocsSection: () => {
          throw new Error('section failed');
        },
      };
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  async function renderDocumentation() {
    const { default: Documentation } = await import('@/pages/Documentation');
    const { render } = await import('@tests/utils');
    return render(<Documentation />);
  }

  function tocButtons() {
    const nav = screen.getByRole('navigation', { name: /table of contents|obsah/i });
    return within(nav).getAllByRole('button');
  }

  describe('in a build without the flag', () => {
    it('keeps the five sections and the five TOC entries, and never imports the guide', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      const { container } = await renderDocumentation();
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      expect(tocButtons()).toHaveLength(5);
      expect(container.querySelector('#assistant')).not.toBeInTheDocument();
      expect(screen.queryByText('Where to find it')).not.toBeInTheDocument();
      expect(guide.loads).toBe(0);
    });
  });

  describe('in a build with the flag', () => {
    it('adds a sixth TOC entry and the section once the guide module has loaded', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { container } = await renderDocumentation();

      expect(await screen.findByRole('heading', { level: 2, name: 'Assistant' })).toBeInTheDocument();
      expect(container.querySelector('#assistant')).toBeInTheDocument();
      expect(tocButtons()).toHaveLength(6);
      expect(within(screen.getByRole('navigation', { name: /table of contents/i })).getByRole('button', { name: 'Assistant' })).toBeInTheDocument();
      expect(screen.getByText('You can send up to 60 messages an hour. When you reach the limit, the assistant tells you how many minutes to wait.')).toBeInTheDocument();
      expect(guide.loads).toBe(1);
    });

    it('shows neither the entry nor the section while the module is still loading', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { container } = await renderDocumentation();

      // First paint, before the import has resolved.
      expect(tocButtons()).toHaveLength(5);
      expect(container.querySelector('#assistant')).not.toBeInTheDocument();
      await screen.findByRole('heading', { level: 2, name: 'Assistant' });
    });

    it('keeps the page intact, with no empty TOC button, when the module fails to load', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      guide.fails = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { container } = await renderDocumentation();
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      const buttons = tocButtons();
      expect(buttons).toHaveLength(5);
      for (const button of buttons) expect(button).toHaveAccessibleName();
      expect(container.querySelector('#assistant')).not.toBeInTheDocument();
      expect(container.querySelectorAll('section[id]')).toHaveLength(5);
      expect(guide.loads).toBe(1);
      consoleError.mockRestore();
    });

    it('drops the TOC entry together with a section that throws while rendering', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      guide.sectionThrows = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { container } = await renderDocumentation();
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      const buttons = tocButtons();
      expect(buttons).toHaveLength(5);
      for (const button of buttons) expect(button).toHaveAccessibleName();
      expect(container.querySelector('#assistant')).not.toBeInTheDocument();
      consoleError.mockRestore();
    });

    it('puts the section between visualization and the glossary', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { container } = await renderDocumentation();
      await screen.findByRole('heading', { level: 2, name: 'Assistant' });

      const ids = Array.from(container.querySelectorAll('section[id]')).map((s) => s.id);
      expect(ids).toEqual(['getting-started', 'expert-opinions', 'results', 'visualization', 'assistant', 'glossary']);
    });

    it('renders the bold UI labels and the link to the privacy notice', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      await renderDocumentation();
      await screen.findByRole('heading', { level: 2, name: 'Assistant' });

      expect(screen.getByText('Explain this result').tagName).toBe('STRONG');
      expect(screen.getByText("Hide my opinions from other members' assistant").tagName).toBe('STRONG');
      expect(screen.getByRole('link', { name: 'Privacy notice' })).toHaveAttribute('href', '/privacy');
    });

    it('points to the header button with its icon instead of a label', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      await renderDocumentation();
      await screen.findByRole('heading', { level: 2, name: 'Assistant' });

      const where = screen.getByText(/Sign in and click the assistant button/);
      expect(where.textContent).toBe("Sign in and click the assistant button  in the top bar. On a project's result page, Explain this result opens the assistant with that project already selected.");
      expect(where.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
      expect(within(where).getByText('Explain this result').tagName).toBe('STRONG');
    });

    it('speaks Czech when the language is Czech', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      const { default: i18n } = await import('@/i18n');
      await i18n.changeLanguage('cs');

      await renderDocumentation();

      expect(await screen.findByRole('heading', { level: 2, name: 'Asistent' })).toBeInTheDocument();
      expect(screen.getByText('Za hodinu můžete poslat nejvýše 60 zpráv. Po dosažení limitu vám asistent řekne, kolik minut počkat.')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Zásady ochrany osobních údajů' })).toHaveAttribute('href', '/privacy');
      const where = screen.getByText(/klikněte na tlačítko asistenta/);
      expect(where.querySelector('svg')).toBeInTheDocument();
      expect(within(where).getByText('Vysvětlit výsledek').tagName).toBe('STRONG');
      await i18n.changeLanguage('en');
    });
  });
});
