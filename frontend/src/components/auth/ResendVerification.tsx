import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SubmitButton } from "@/components/forms";
import { api } from "@/lib/api";

interface ResendVerificationProps {
  readonly email: string;
  readonly password: string;
}

type ResendStatus = "idle" | "success" | "error";

/**
 * Resend affordance for a fresh activation link. Only ever rendered where the
 * caller has just collected the account's password (the check-your-inbox
 * state right after registration, or a login blocked by an unverified
 * account). See api.resendVerification, which requires that password too.
 */
export function ResendVerification({ email, password }: ResendVerificationProps) {
  const { t } = useTranslation("auth");
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<ResendStatus>("idle");

  const handleResend = async () => {
    setIsLoading(true);
    try {
      await api.resendVerification(email, password);
      setStatus("success");
    } catch {
      setStatus("error");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-2 text-center">
      <SubmitButton
        type="button"
        variant="outline"
        className="w-full"
        isLoading={isLoading}
        loadingText={t("resendVerification.sending")}
        onClick={handleResend}
      >
        {t("resendVerification.action")}
      </SubmitButton>
      {status === "success" && (
        <p role="status" className="text-sm text-success">
          {t("resendVerification.success")}
        </p>
      )}
      {status === "error" && (
        <p role="alert" className="text-sm text-destructive">
          {t("resendVerification.error")}
        </p>
      )}
    </div>
  );
}
