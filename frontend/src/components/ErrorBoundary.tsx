import { Component, type ErrorInfo, type ReactNode } from 'react';
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
 * The fallback text is hardcoded in English rather than translated: i18n itself
 * could be the thing that failed, so the boundary must not depend on it.
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
          <h1 className="text-2xl font-semibold">Something went wrong</h1>
          <p className="text-muted-foreground">
            An unexpected error occurred. Please reload the page to continue.
          </p>
          <button
            type="button"
            onClick={this.handleReload}
            className="rounded-md bg-primary px-4 py-2 text-primary-foreground"
          >
            Reload page
          </button>
        </main>
      );
    }

    return this.props.children;
  }
}
