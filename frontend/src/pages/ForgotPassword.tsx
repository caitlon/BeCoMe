import { useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import {
  FormField,
  SubmitButton,
  TurnstileField,
  TurnstileFieldHandle,
} from "@/components/forms";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { describeError } from "@/lib/errorMessages";
import { isTurnstileRefusal } from "@/lib/errors";
import { isTurnstileRequired } from "@/lib/turnstile";

type ForgotPasswordFormData = {
  email: string;
};

const ForgotPassword = () => {
  const { t } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.forgotPassword"));

  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const turnstileRef = useRef<TurnstileFieldHandle>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const awaitingTurnstile = isTurnstileRequired() && turnstileToken === null;

  const schema = useMemo(
    () =>
      z.object({
        email: z.email(t("validation.emailInvalid")),
      }),
    [t]
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(schema),
    mode: "onTouched",
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setIsLoading(true);
    try {
      await api.forgotPassword(data.email, turnstileToken);
      setSubmitted(true);
    } catch (error) {
      // A refused bot check is the one failure this screen must not hide. It is
      // decided before the address is ever looked at, so saying it out loud reveals
      // nothing about whether an account exists — while the confirmation panel would
      // claim a link is on its way when nothing was sent, and unmount the widget, so
      // the user could not even earn a fresh challenge to retry with.
      if (isTurnstileRefusal(error)) {
        turnstileRef.current?.reset();
        setTurnstileToken(null);
        toast({
          title: t("forgotPassword.errorTitle"),
          description: describeError(error, tCommon, tCommon("errors.turnstileRefused")),
          variant: "destructive",
        });
        return;
      }
      // Everything else is swallowed on purpose: the screen must look identical
      // whether or not the address exists, mirroring the backend's 202-always answer.
      setSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  if (submitted) {
    return (
      <AuthLayout title={t("forgotPassword.successTitle")}>
        <p className="text-center text-sm text-muted-foreground">
          {t("forgotPassword.successMessage")}
        </p>
        <p className="text-center text-sm text-muted-foreground mt-6">
          <Link to="/login" className="text-foreground hover:underline">
            {t("forgotPassword.backToLogin")}
          </Link>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t("forgotPassword.title")}>
      <p className="text-sm text-muted-foreground mb-4">
        {t("forgotPassword.description")}
      </p>
      {/* eslint-disable-next-line react-hooks/refs -- handleSubmit defers to the browser's submit event; turnstileRef is only read/written once that event fires, never during render */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          label={t("forgotPassword.email")}
          type="email"
          autoComplete="email"
          placeholder={t("forgotPassword.emailPlaceholder")}
          error={errors.email}
          {...register("email")}
        />

        <TurnstileField
          action="password_reset"
          ref={turnstileRef}
          onToken={setTurnstileToken}
        />

        <SubmitButton
          className="w-full"
          isLoading={isLoading}
          loadingText={t("forgotPassword.submitting")}
          disabled={awaitingTurnstile}
        >
          {t("forgotPassword.submit")}
        </SubmitButton>
      </form>

      <p className="text-center text-sm text-muted-foreground mt-6">
        <Link to="/login" className="text-foreground hover:underline">
          {t("forgotPassword.backToLogin")}
        </Link>
      </p>
    </AuthLayout>
  );
};

export default ForgotPassword;
