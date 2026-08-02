/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** Sentry DSN for the browser SDK. Absent means error tracking stays off. */
  readonly VITE_SENTRY_DSN?: string;
  /** Environment tag on Sentry events: dev, test, or prod. */
  readonly VITE_APP_ENV?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
