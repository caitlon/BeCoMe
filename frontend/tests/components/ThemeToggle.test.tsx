import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeToggle } from '@/components/ThemeToggle';

const mockSetTheme = vi.fn();
let mockTheme = 'light';

vi.mock('@/components/ThemeProvider', () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
  }),
}));

describe('ThemeToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTheme = 'light';
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
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole('button'));

    expect(mockSetTheme).toHaveBeenCalledWith('light');
  });
});
