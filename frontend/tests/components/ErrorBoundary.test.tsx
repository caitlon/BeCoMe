import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import i18n from '@/i18n';

function Boom(): never {
  throw new Error('render explosion');
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <p>safe content</p>
      </ErrorBoundary>
    );

    expect(screen.getByText('safe content')).toBeInTheDocument();
  });

  it('renders an alert fallback when a child throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it('renders the translated fallback for the active language', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await i18n.changeLanguage('cs');

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );

    expect(screen.getByText('Něco se pokazilo')).toBeInTheDocument();
  });

  it('logs the rendering error', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );

    const loggedReactError = errorSpy.mock.calls.some(
      (call) => typeof call[0] === 'string' && call[0].includes('React rendering error')
    );
    expect(loggedReactError).toBe(true);
  });
});
