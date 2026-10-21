import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, screen, within } from '@testing-library/react';
import { framerMotionMock, unauthenticatedAuthMock } from '@tests/utils';

vi.mock('@/contexts/AuthContext', () => unauthenticatedAuthMock);

vi.mock('framer-motion', () => framerMotionMock);

describe('Documentation assistant section', () => {
  beforeEach(() => {
    // The slots compute their build flag once at module scope, so the page and
    // the helpers that share its i18n instance are re-imported per test.
    vi.resetModules();
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
    it('keeps the five sections and the five TOC entries', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');
      // Already loaded, so a gate that wrongly let the slot through would render
      // the section within one flush instead of staying pending forever.
      await import('@/components/assistant/AssistantGuide');

      const { container } = await renderDocumentation();
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      expect(tocButtons()).toHaveLength(5);
      expect(container.querySelector('#assistant')).not.toBeInTheDocument();
      expect(screen.queryByText('Where to find it')).not.toBeInTheDocument();
    });
  });

  describe('in a build with the flag', () => {
    it('adds a sixth TOC entry and the section once the lazy chunk resolves', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { container } = await renderDocumentation();

      expect(await screen.findByRole('heading', { level: 2, name: 'Assistant' })).toBeInTheDocument();
      expect(container.querySelector('#assistant')).toBeInTheDocument();
      expect(tocButtons()).toHaveLength(6);
      expect(within(screen.getByRole('navigation', { name: /table of contents/i })).getByRole('button', { name: 'Assistant' })).toBeInTheDocument();
      expect(screen.getByText('You can send up to 60 messages an hour. When you reach the limit, the assistant tells you how many minutes to wait.')).toBeInTheDocument();
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

    it('speaks Czech when the language is Czech', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      const { default: i18n } = await import('@/i18n');
      await i18n.changeLanguage('cs');

      await renderDocumentation();

      expect(await screen.findByRole('heading', { level: 2, name: 'Asistent' })).toBeInTheDocument();
      expect(screen.getByText('Za hodinu můžete poslat nejvýše 60 zpráv. Po dosažení limitu vám asistent řekne, kolik minut počkat.')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Zásady ochrany osobních údajů' })).toHaveAttribute('href', '/privacy');
      await i18n.changeLanguage('en');
    });
  });
});
