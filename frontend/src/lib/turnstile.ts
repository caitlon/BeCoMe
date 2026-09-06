/**
 * The half of the Cloudflare Turnstile integration that is not React: which sitekey this
 * build was given, and one shared copy of Cloudflare's script.
 *
 * An empty sitekey means the check is off. That is the state local development, vitest
 * and Playwright run in: no widget is drawn, no token is minted, and the auth forms
 * submit exactly as they did before. It pairs with the API's own `TURNSTILE_ENABLED`,
 * which is what actually decides whether a token is demanded; a build with no sitekey
 * against an API with the check on is a misconfiguration, not a supported mode.
 *
 * The script is fetched once per page and reused by every widget on it. `render=explicit`
 * stops it drawing anything by itself: the auth forms mount long after page load, so each
 * widget is rendered by hand once its container exists.
 */

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

/**
 * The form a token is minted for, named exactly as the API's route guards declare it
 * (`require_human(...)` in api/routes/auth.py).
 *
 * Cloudflare echoes this back to the API from siteverify, and the API refuses a token
 * whose action is not the one its own endpoint declared. That is what stops a token
 * farmed from the sign-in form opening registration: the sitekey is public, so minting
 * a token elsewhere is easy, and the action is what says which door it opens. The names
 * must match the backend's strings character for character -- note `password_reset`
 * against the `/auth/forgot-password` route -- because a mismatch is refused as a 403
 * that deliberately says nothing about why.
 */
export type TurnstileAction =
  | "register"
  | "login"
  | "password_reset"
  | "resend_verification";

/** Options Cloudflare's `render()` is called with. Hyphenated keys are its own naming. */
export interface TurnstileRenderOptions {
  readonly sitekey: string;
  readonly action: TurnstileAction;
  readonly theme: "light" | "dark" | "auto";
  readonly language: string;
  readonly callback: (token: string) => void;
  readonly "error-callback": () => void;
  readonly "expired-callback": () => void;
}

/** The subset of `window.turnstile` this app uses. */
export interface TurnstileApi {
  /** Draws a widget into `container`; returns its id, or undefined if it could not. */
  render(container: HTMLElement, options: TurnstileRenderOptions): string | undefined;
  /** Discards the widget's current token and starts a fresh challenge. */
  reset(widgetId: string): void;
  /** Tears the widget down, freeing what Cloudflare's script holds for it. */
  remove(widgetId: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

/** The sitekey this build renders, or an empty string when it was given none. */
export function getTurnstileSiteKey(): string {
  return import.meta.env.VITE_TURNSTILE_SITE_KEY ?? "";
}

/**
 * Whether a form must hold a token before it may be submitted.
 *
 * Read at render time rather than at module load so a build without a sitekey stays a
 * first-class path instead of something baked in at import.
 */
export function isTurnstileRequired(): boolean {
  return getTurnstileSiteKey() !== "";
}

let scriptLoad: Promise<TurnstileApi> | null = null;

/**
 * Resolves with Cloudflare's widget API, loading the script on first use.
 *
 * Every caller after the first shares the same promise, so four auth forms on one page
 * produce one script tag. A failed load drops the shared promise, letting a later mount
 * try the network again instead of inheriting the failure for the life of the page.
 */
export function loadTurnstileScript(): Promise<TurnstileApi> {
  const loaded = window.turnstile;
  if (loaded) {
    return Promise.resolve(loaded);
  }

  scriptLoad ??= new Promise<TurnstileApi>((resolve, reject) => {
    const script = document.createElement("script");

    const fail = (message: string) => {
      scriptLoad = null;
      script.remove();
      reject(new Error(message));
    };

    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => {
      const api = window.turnstile;
      if (api) {
        resolve(api);
        return;
      }
      // A 200 that is not Cloudflare's script: a captive portal or a proxy error page.
      fail("Turnstile script loaded without defining window.turnstile");
    });
    script.addEventListener("error", () => fail("Turnstile script failed to load"));

    document.head.append(script);
  });

  return scriptLoad;
}
