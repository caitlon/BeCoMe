import { useTranslation } from "react-i18next";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ServiceUnavailableProps {
  readonly onRetry: () => void;
}

/**
 * Shown by ProtectedRoute instead of a redirect when the session probe fails
 * with a network/server error: the user's login state is simply unknown, so
 * bouncing them to /login could sign out someone who is actually logged in.
 */
export function ServiceUnavailable({ onRetry }: ServiceUnavailableProps) {
  const { t: tCommon } = useTranslation();

  return (
    <main
      id="main-content"
      role="alert"
      className="min-h-screen flex flex-col items-center justify-center gap-4 p-6 text-center"
    >
      <AlertTriangle className="h-8 w-8 text-muted-foreground" />
      <p className="text-muted-foreground max-w-sm">{tCommon("errors.serviceUnavailable")}</p>
      <Button onClick={onRetry}>{tCommon("errors.retry")}</Button>
    </main>
  );
}
