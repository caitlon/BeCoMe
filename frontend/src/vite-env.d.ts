/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** Sentry DSN for the browser SDK. Absent means error tracking stays off. */
  readonly VITE_SENTRY_DSN?: string;
  /** Environment tag on Sentry events: dev, test, or prod. */
  readonly VITE_APP_ENV?: string;
  /** Cloudflare Turnstile sitekey. Absent or empty means the bot check stays off. */
  readonly VITE_TURNSTILE_SITE_KEY?: string;
  /**
   * Build-time kill switch for the AI assistant. Only the exact string `true`
   * includes it: set in a developer's frontend/.env.development.local or on the
   * dev and test frontend services, left unset in prod. See components/assistant/index.tsx.
   */
  readonly VITE_ASSISTANT_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
