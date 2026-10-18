import { Navigate } from "react-router";
import { useAuth } from "@/contexts/AuthContext";

interface GuestRouteProps {
  readonly children: React.ReactNode;
}

export function GuestRoute({ children }: GuestRouteProps) {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/projects" replace />;
  }

  // Loading renders the page too: login() re-probes the session during a form
  // submit, and unmounting the form at that moment would break the submit.
  // An unknown state (unauthenticated, service unavailable) is no reason to
  // keep a visitor away from the sign-in form either.
  return <>{children}</>;
}
