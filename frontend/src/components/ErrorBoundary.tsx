import { Component, type ErrorInfo, type ReactNode } from 'react';
import * as Sentry from '@sentry/react';
import i18n from '@/i18n';
import { logger } from '@/lib/logger';

interface ErrorBoundaryProps {
  readonly children: ReactNode;
}

interface ErrorBoundaryState {
  readonly hasError: boolean;
}

/**
 * Catches rendering errors anywhere below it and shows a recovery screen.
 *
 * Fallback text is read from the i18n singleton via `i18n.t` rather than the
 * `useTranslation` hook: a class component cannot call hooks, and reading the
 * singleton directly keeps the boundary independent of React context, so it
 * still renders correctly even if a context provider is what failed.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    logger.error('React rendering error', {
      error: error.message,
      componentStack: info.componentStack,
    });
    // Forward to Sentry: a caught render error never reaches the global handler,
    // so without this the most catastrophic frontend failures stay invisible.
    Sentry.captureException(error, {
      contexts: { react: { componentStack: info.componentStack } },
    });
  }

  private readonly handleReload = (): void => {
    globalThis.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main
          id="main-content"
          role="alert"
          className="min-h-screen flex flex-col items-center justify-center gap-4 p-6 text-center"
        >
          <h1 className="text-2xl font-semibold">{i18n.t('errorBoundary.title')}</h1>
          <p className="text-muted-foreground">{i18n.t('errorBoundary.description')}</p>
          <button
            type="button"
            onClick={this.handleReload}
            className="rounded-md bg-primary px-4 py-2 text-primary-foreground"
          >
            {i18n.t('errorBoundary.reload')}
          </button>
        </main>
      );
    }

    return this.props.children;
  }
}
