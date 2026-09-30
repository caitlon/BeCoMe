import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@tests/utils';
import { ServiceUnavailable } from '@/components/auth/ServiceUnavailable';

describe('ServiceUnavailable', () => {
  it('renders a focusable main#main-content so the skip link has a target', () => {
    render(<ServiceUnavailable onRetry={vi.fn()} />);

    const main = screen.getByRole('alert');
    expect(main.tagName).toBe('MAIN');
    expect(main).toHaveAttribute('id', 'main-content');
    expect(main).toHaveAttribute('tabindex', '-1');
  });
});
