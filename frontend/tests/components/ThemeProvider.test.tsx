import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider, useTheme } from '@/components/ThemeProvider';

function ThemeConsumer() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button type="button" onClick={() => setTheme('dark')}>Set Dark</button>
      <button type="button" onClick={() => setTheme('light')}>Set Light</button>
    </div>
  );
}

/**
 * Builds a mutable matchMedia mock that records the "change" listener so
 * tests can simulate the OS switching color scheme at runtime.
 */
function createMatchMediaMock(matches: boolean) {
  const listeners = new Map<string, EventListener>();
  const mql = {
    matches,
    media: '(prefers-color-scheme: dark)',
    addEventListener: vi.fn((event: string, listener: EventListener) => {
      listeners.set(event, listener);
    }),
    removeEventListener: vi.fn((event: string) => {
      listeners.delete(event);
    }),
  };
  return { mql, listeners };
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('light', 'dark');
  });

  it('falls back to defaultTheme when localStorage is empty', () => {
    render(
      <ThemeProvider defaultTheme="light">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('theme')).toHaveTextContent('light');
  });

  it('reads theme from localStorage on mount', () => {
    localStorage.setItem('vite-ui-theme', 'dark');

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('theme')).toHaveTextContent('dark');
  });

  it('setTheme persists to localStorage', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider defaultTheme="light">
        <ThemeConsumer />
      </ThemeProvider>
    );

    await user.click(screen.getByRole('button', { name: 'Set Dark' }));

    expect(localStorage.getItem('vite-ui-theme')).toBe('dark');
  });

  it('adds "dark" class to documentElement for dark theme', () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('dark');
  });

  it('adds "light" class to documentElement for light theme', () => {
    render(
      <ThemeProvider defaultTheme="light">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light');
  });

  it('removes previous class when theme changes', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider defaultTheme="light">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(document.documentElement.classList.contains('light')).toBe(true);

    await user.click(screen.getByRole('button', { name: 'Set Dark' }));

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
  });

  it('detects system preference via matchMedia for "system" theme', () => {
    const { mql } = createMatchMediaMock(true);
    const matchMediaSpy = vi.spyOn(window, 'matchMedia')
      .mockReturnValue(mql as unknown as MediaQueryList);

    render(
      <ThemeProvider defaultTheme="system">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('dark');
    matchMediaSpy.mockRestore();
  });

  it('resolves "light" when theme is "system" and the OS prefers light', () => {
    const { mql } = createMatchMediaMock(false);
    const matchMediaSpy = vi.spyOn(window, 'matchMedia')
      .mockReturnValue(mql as unknown as MediaQueryList);

    render(
      <ThemeProvider defaultTheme="system">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light');
    matchMediaSpy.mockRestore();
  });

  it('updates resolvedTheme when the OS color scheme changes while theme is "system"', () => {
    const { mql, listeners } = createMatchMediaMock(false);
    const matchMediaSpy = vi.spyOn(window, 'matchMedia')
      .mockReturnValue(mql as unknown as MediaQueryList);

    render(
      <ThemeProvider defaultTheme="system">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light');

    act(() => {
      mql.matches = true;
      listeners.get('change')?.(new Event('change'));
    });

    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);

    act(() => {
      mql.matches = false;
      listeners.get('change')?.(new Event('change'));
    });

    expect(screen.getByTestId('resolved-theme')).toHaveTextContent('light');
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    matchMediaSpy.mockRestore();
  });

  it('removes the matchMedia change listener on cleanup when theme is "system"', () => {
    const { mql } = createMatchMediaMock(false);
    const matchMediaSpy = vi.spyOn(window, 'matchMedia')
      .mockReturnValue(mql as unknown as MediaQueryList);

    const { unmount } = render(
      <ThemeProvider defaultTheme="system">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(mql.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));

    unmount();

    expect(mql.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
    matchMediaSpy.mockRestore();
  });

  it('does not subscribe to matchMedia changes when theme is not "system"', () => {
    const { mql } = createMatchMediaMock(false);
    const matchMediaSpy = vi.spyOn(window, 'matchMedia')
      .mockReturnValue(mql as unknown as MediaQueryList);

    render(
      <ThemeProvider defaultTheme="light">
        <ThemeConsumer />
      </ThemeProvider>
    );

    expect(mql.addEventListener).not.toHaveBeenCalled();
    matchMediaSpy.mockRestore();
  });

  it('uses default "system" theme outside ThemeProvider', () => {
    render(<ThemeConsumer />);

    // createContext has initialState with theme: "system"
    expect(screen.getByTestId('theme')).toHaveTextContent('system');
  });

  it('default context setTheme is a no-op outside ThemeProvider', async () => {
    const user = userEvent.setup();

    render(<ThemeConsumer />);

    // Clicking the button calls the no-op setTheme from initialState
    await user.click(screen.getByRole('button', { name: 'Set Dark' }));

    // Theme stays "system", since the no-op does nothing
    expect(screen.getByTestId('theme')).toHaveTextContent('system');
  });

  it('respects custom storageKey', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider defaultTheme="light" storageKey="my-theme">
        <ThemeConsumer />
      </ThemeProvider>
    );

    await user.click(screen.getByRole('button', { name: 'Set Dark' }));

    expect(localStorage.getItem('my-theme')).toBe('dark');
    expect(localStorage.getItem('vite-ui-theme')).toBeNull();
  });
});
