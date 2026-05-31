import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '@/components/ErrorBoundary';

function Boom(): never {
  throw new Error('render explosion');
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
