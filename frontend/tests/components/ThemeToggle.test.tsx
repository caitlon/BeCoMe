import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen } from '@tests/utils';
import { ThemeToggle } from '@/components/ThemeToggle';

const mockSetTheme = vi.fn();
let mockTheme = 'light';
let mockResolvedTheme = 'light';

vi.mock('@/components/ThemeProvider', () => ({
  useTheme: () => ({
    theme: mockTheme,
    resolvedTheme: mockResolvedTheme,
    setTheme: mockSetTheme,
  }),
}));

describe('ThemeToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTheme = 'light';
    mockResolvedTheme = 'light';
  });

  it('renders button with sr-only text', () => {
    render(<ThemeToggle />);

    expect(screen.getByRole('button')).toBeInTheDocument();
    expect(screen.getByText('Toggle theme')).toBeInTheDocument();
  });

  it('has accessible aria-label', () => {
    render(<ThemeToggle />);

    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-label',
      'Switch to dark mode'
    );
  });

  it('toggles light to dark on click', async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole('button'));

    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });

  it('toggles dark to light on click', async () => {
    mockTheme = 'dark';
    mockResolvedTheme = 'dark';
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole('button'));

    expect(mockSetTheme).toHaveBeenCalledWith('light');
  });

  it('resolves theme="system" with a light OS preference to a light toggle state', async () => {
    mockTheme = 'system';
    mockResolvedTheme = 'light';
    const user = userEvent.setup();
    render(<ThemeToggle />);

    // Bug regression: on a light OS with theme="system", the very first click
    // must flip to dark, and the label must not already read "switch to light".
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Switch to dark mode');

    await user.click(screen.getByRole('button'));

    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });

  it('resolves theme="system" with a dark OS preference to a dark toggle state', async () => {
    mockTheme = 'system';
    mockResolvedTheme = 'dark';
    const user = userEvent.setup();
    render(<ThemeToggle />);

    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Switch to light mode');

    await user.click(screen.getByRole('button'));

    expect(mockSetTheme).toHaveBeenCalledWith('light');
  });
});
