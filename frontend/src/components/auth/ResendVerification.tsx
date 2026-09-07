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
    } finally {
      setIsLoading(false);
      // Unlike the three auth pages, this control stays on screen whatever happened:
      // after a failure for the retry it invites, after a success so a second link can
      // be asked for. The attempt spent its token either way, so both paths have to
      // earn a fresh one or the next send is refused for a reason nobody can act on.
      turnstileRef.current?.reset();
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
