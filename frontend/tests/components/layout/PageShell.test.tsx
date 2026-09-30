import { describe, it, expect, vi } from 'vitest';
import { render, framerMotionMock } from '@tests/utils';
import { PageShell } from '@/components/layout/PageShell';

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    logout: vi.fn(),
  }),
}));

vi.mock('framer-motion', () => framerMotionMock);

describe('PageShell', () => {
  // The skip link is a fragment link: the browser moves focus to its target only
  // when the target is focusable, so <main> needs tabindex from the first render.
  it.each(['app', 'content', 'centered'] as const)(
    'renders a focusable main#main-content in the %s variant',
    (variant) => {
      const { container } = render(<PageShell variant={variant}>content</PageShell>);

      const main = container.querySelector('main#main-content');
      expect(main).not.toBeNull();
      expect(main).toHaveAttribute('tabindex', '-1');
    }
  );
});
