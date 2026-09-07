/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** Sentry DSN for the browser SDK. Absent means error tracking stays off. */
  readonly VITE_SENTRY_DSN?: string;
  /** Environment tag on Sentry events: dev, test, or prod. */
  readonly VITE_APP_ENV?: string;
  /** Cloudflare Turnstile sitekey. Absent or empty means the bot check stays off. */
  readonly VITE_TURNSTILE_SITE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
