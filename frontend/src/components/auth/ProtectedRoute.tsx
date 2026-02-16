import { Navigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  readonly children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <output
        aria-label={t("a11y.loading")}
        aria-live="polite"
        className="min-h-screen flex items-center justify-center"
      >
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </output>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
