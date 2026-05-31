/**
 * Lightweight client-side logger.
 *
 * In development every level reaches the console. In production only `warn`
 * and `error` are emitted, keeping the console quiet for end users while still
 * surfacing problems worth reporting.
 */

type LogContext = Record<string, unknown>;

const isDev = (): boolean => import.meta.env.DEV;

export const logger = {
  debug(message: string, context?: LogContext): void {
    if (isDev()) {
      console.debug(`[DEBUG] ${message}`, context ?? '');
    }
  },

  info(message: string, context?: LogContext): void {
    if (isDev()) {
      console.info(`[INFO] ${message}`, context ?? '');
    }
  },

  warn(message: string, context?: LogContext): void {
    console.warn(`[WARN] ${message}`, context ?? '');
  },

  error(message: string, context?: LogContext): void {
    console.error(`[ERROR] ${message}`, context ?? '');
  },
};
