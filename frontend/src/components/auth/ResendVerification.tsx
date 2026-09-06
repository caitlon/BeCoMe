import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { SubmitButton, TurnstileField, TurnstileFieldHandle } from "@/components/forms";
import { api } from "@/lib/api";
import { isTurnstileRequired } from "@/lib/turnstile";

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

  const turnstileRef = useRef<TurnstileFieldHandle>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const awaitingTurnstile = isTurnstileRequired() && turnstileToken === null;

  const handleResend = async () => {
    setIsLoading(true);
    try {
      await api.resendVerification(email, password, turnstileToken);
      setStatus("success");
    } catch {
      setStatus("error");
      // The control stays on screen after a failure, so the retry it invites needs
      // a token that has not already been spent.
      turnstileRef.current?.reset();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-2 text-center">
      <TurnstileField action="resend_verification" ref={turnstileRef} onToken={setTurnstileToken} />
      <SubmitButton
        type="button"
        variant="outline"
        className="w-full"
        isLoading={isLoading}
        loadingText={t("resendVerification.sending")}
        onClick={handleResend}
        disabled={awaitingTurnstile}
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
