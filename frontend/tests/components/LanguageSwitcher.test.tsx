import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import i18n from '@/i18n';

// Mock i18n with hoisted variables
const { mockI18n, mockChangeLanguage } = vi.hoisted(() => {
  const changeLanguage = vi.fn();
  return {
    mockChangeLanguage: changeLanguage,
    mockI18n: {
      resolvedLanguage: 'en',
      language: 'en',
      changeLanguage,
    },
  };
});

// Only the resolvedLanguage/language/changeLanguage trio is faked (so the
// resolvedLanguage-fallback branches below stay easy to drive); `t` stays
// the real hook so the aria-label is checked against the actual translations.
vi.mock('react-i18next', async () => {
  const actual = await vi.importActual<typeof import('react-i18next')>('react-i18next');
  return {
    ...actual,
    useTranslation: (...args: Parameters<typeof actual.useTranslation>) => ({
      ...actual.useTranslation(...args),
      i18n: mockI18n,
    }),
  };
});

describe('LanguageSwitcher', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockI18n.resolvedLanguage = 'en';
    mockI18n.language = 'en';
  });

  it('renders current language label', () => {
    render(<LanguageSwitcher />);

    expect(screen.getByText('EN')).toBeInTheDocument();
  });

  it('has accessible label for switching', () => {
    render(<LanguageSwitcher />);

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', 'Switch to Čeština');
  });

  it('translates the accessible label when the UI language is Czech', async () => {
    await i18n.changeLanguage('cs');
    try {
      const { unmount } = render(<LanguageSwitcher />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Přepnout na Čeština');

      // Unmount before reverting the language so the language change below
      // does not re-render this already-asserted component outside act().
      unmount();
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('calls changeLanguage with "cs" when current is "en"', async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher />);

    await user.click(screen.getByRole('button'));

    expect(mockChangeLanguage).toHaveBeenCalledWith('cs');
  });

  it('shows CS and switches to EN when language is Czech', async () => {
    mockI18n.resolvedLanguage = 'cs';
    mockI18n.language = 'cs';

    const user = userEvent.setup();
    render(<LanguageSwitcher />);

    expect(screen.getByText('CS')).toBeInTheDocument();

    await user.click(screen.getByRole('button'));

    expect(mockChangeLanguage).toHaveBeenCalledWith('en');
  });

  it('handles language with region code (e.g., cs-CZ)', async () => {
    mockI18n.resolvedLanguage = 'cs-CZ';
    mockI18n.language = 'cs-CZ';

    render(<LanguageSwitcher />);

    // Should extract "cs" from "cs-CZ" and show CS
    expect(screen.getByText('CS')).toBeInTheDocument();
  });

  it('falls back to i18n.language when resolvedLanguage is undefined', () => {
    mockI18n.resolvedLanguage = undefined as unknown as string;
    mockI18n.language = 'en';

    render(<LanguageSwitcher />);

    expect(screen.getByText('EN')).toBeInTheDocument();
  });

  it('defaults to EN for unknown language codes', () => {
    mockI18n.resolvedLanguage = 'de';
    mockI18n.language = 'de';

    render(<LanguageSwitcher />);

    // Unknown language should default to "en"
    expect(screen.getByText('EN')).toBeInTheDocument();
  });
});
