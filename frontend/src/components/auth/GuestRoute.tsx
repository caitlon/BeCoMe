import { Navigate, useLocation } from "react-router";
import { useAuth } from "@/contexts/AuthContext";

interface GuestRouteProps {
  readonly children: React.ReactNode;
}

// ProtectedRoute leaves the page the visitor wanted in location state. It is
// accepted only if parsing it the way a browser does stays on this origin:
// "//host", "/\host" and a "/" followed by a tab or newline (which the URL
// parser strips) all resolve to another origin there, and pushing such a URL
// to the history throws.
function returnTarget(from: unknown): string | null {
  if (typeof from !== "object" || from === null) return null;
  const { pathname, search, hash } = from as Record<string, unknown>;
  if (typeof pathname !== "string" || !pathname.startsWith("/")) return null;
  const path =
    pathname + (typeof search === "string" ? search : "") + (typeof hash === "string" ? hash : "");
  let url: URL;
  try {
    url = new URL(path, globalThis.location.origin);
  } catch {
    // "//host:99999" and the like do not parse at all.
    return null;
  }
  if (url.origin !== globalThis.location.origin) return null;
  return url.pathname + url.search + url.hash;
}

export function GuestRoute({ children }: GuestRouteProps) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (isAuthenticated) {
    const target = returnTarget((location.state as { from?: unknown } | null)?.from);
    return <Navigate to={target ?? "/projects"} replace />;
  }

  // Loading renders the page too: login() re-probes the session during a form
  // submit, and unmounting the form at that moment would break the submit.
  // An unknown state (unauthenticated, service unavailable) is no reason to
  // keep a visitor away from the sign-in form either.
  return <>{children}</>;
}
