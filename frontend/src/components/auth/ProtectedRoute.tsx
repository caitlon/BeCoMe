import { Navigate, useLocation } from "react-router";
import { useAuth } from "@/contexts/AuthContext";
import { ServiceUnavailable } from "@/components/auth/ServiceUnavailable";
import { PageLoader } from "@/components/PageLoader";

interface ProtectedRouteProps {
  readonly children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, isServiceUnavailable, refreshUser } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <PageLoader />;
  }

  // A network/server failure while probing the session leaves the login state
  // unknown; offer a retry instead of a redirect, which would incorrectly
  // sign out anyone who actually has a valid session.
  if (isServiceUnavailable) {
    return <ServiceUnavailable onRetry={refreshUser} />;
  }

  if (!isAuthenticated) {
    // The placeholder stays the skip link's target until the login page renders.
    return (
      <>
        <PageLoader />
        <Navigate to="/login" state={{ from: location }} replace />
      </>
    );
  }

  return <>{children}</>;
}
