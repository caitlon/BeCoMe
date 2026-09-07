import * as React from "react";
import { useTranslation } from "react-i18next";

import { useTheme } from "@/components/ThemeProvider";
import {
  getTurnstileSiteKey,
  loadTurnstileScript,
  TurnstileAction,
  TurnstileApi,
} from "@/lib/turnstile";
import { cn } from "@/lib/utils";

/** What a form holding this widget can ask it to do. */
export interface TurnstileFieldHandle {
  /**
   * Drops the current token and starts a fresh challenge.
   *
   * A token is spent by the submission that carried it and expires after five minutes,
   * so a form that failed must reset before the user tries again; otherwise the second
   * attempt sends a dead token and is refused for a reason that has nothing to do with
   * what the user typed.
   */
  reset(): void;
}

interface TurnstileFieldProps {
  /** Which form this is, so the token it mints only opens that form's endpoint. */
  readonly action: TurnstileAction;
  /** Called with the token whenever there is one, and with null whenever there is not. */
  readonly onToken: (token: string | null) => void;
  readonly className?: string;
}

/**
 * The Cloudflare Turnstile widget for the four auth forms open to anonymous callers.
 *
 * Renders nothing at all when the build has no sitekey, which is how local development
 * and the test suites keep working: the parent's token stays null, and
 * `isTurnstileRequired()` is what tells it that null is fine.
 *
 * The widget is drawn by an effect rather than by markup because Cloudflare's script is
 * loaded in explicit mode and the container has to exist first. Theme and language are
 * fixed at render time by Cloudflare, so changing either rebuilds the widget: the effect
 * clears the token on the way out and the new widget mints another.
 */
const TurnstileField = React.forwardRef<TurnstileFieldHandle, TurnstileFieldProps>(
  ({ action, onToken, className }, ref) => {
    const { t, i18n } = useTranslation("auth");
    const { resolvedTheme } = useTheme();
    const siteKey = getTurnstileSiteKey();
    const language = i18n.resolvedLanguage ?? "auto";

    const containerRef = React.useRef<HTMLDivElement>(null);
    const widgetRef = React.useRef<{ api: TurnstileApi; id: string } | null>(null);
    const [failed, setFailed] = React.useState(false);

    // Read through a ref so a parent that re-renders with a new callback identity does
    // not re-run the effect below and throw away a token the user already earned.
    const onTokenRef = React.useRef(onToken);
    React.useEffect(() => {
      onTokenRef.current = onToken;
    }, [onToken]);

    // Shared by the parent's reset() and by the widget's own expiry callback: both mean
    // "the token we had is no longer worth sending, go and earn another".
    const resetWidget = React.useCallback(() => {
      onTokenRef.current(null);
      const widget = widgetRef.current;
      if (widget) {
        widget.api.reset(widget.id);
      }
    }, []);

    React.useImperativeHandle(ref, () => ({ reset: resetWidget }), [resetWidget]);

    React.useEffect(() => {
      if (siteKey === "") {
        return;
      }
      const container = containerRef.current;
      /* v8 ignore next 3 -- the container is in the DOM before any effect runs */
      if (container === null) {
        return;
      }

      // This effect runs again whenever the widget has to be rebuilt (theme, language,
      // action, sitekey), and the new widget has not failed at anything yet.
      setFailed(false);

      let active = true;

      loadTurnstileScript()
        .then((api) => {
          // The form was closed while the script was in flight; drawing a widget into a
          // detached node would leave Cloudflare holding it for the life of the page.
          if (!active) {
            return;
          }
          const id = api.render(container, {
            sitekey: siteKey,
            action,
            theme: resolvedTheme,
            language,
            callback: (token) => {
              setFailed(false);
              onTokenRef.current(token);
            },
            "error-callback": () => {
              setFailed(true);
              onTokenRef.current(null);
            },
            // Five minutes have passed with the form still open. Dropping the token
            // re-disables submit, and the fresh challenge replaces it in the meantime.
            "expired-callback": resetWidget,
          });
          if (id === undefined) {
            setFailed(true);
            return;
          }
          widgetRef.current = { api, id };
        })
        .catch(() => setFailed(true));

      return () => {
        active = false;
        const widget = widgetRef.current;
        widgetRef.current = null;
        onTokenRef.current(null);
        if (widget) {
          widget.api.remove(widget.id);
        }
      };
    }, [siteKey, action, resolvedTheme, language, resetWidget]);

    if (siteKey === "") {
      return null;
    }

    return (
      <div className={cn("space-y-2", className)}>
        <div ref={containerRef} />
        {failed && (
          <p role="alert" className="text-sm text-destructive">
            {t("turnstile.error")}
          </p>
        )}
      </div>
    );
  }
);
TurnstileField.displayName = "TurnstileField";

export { TurnstileField };
