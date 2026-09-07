import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import { FormField, SubmitButton, TurnstileField } from "@/components/forms";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { api } from "@/lib/api";
import { isTurnstileRequired } from "@/lib/turnstile";

type ForgotPasswordFormData = {
  email: string;
};

const ForgotPassword = () => {
  const { t } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.forgotPassword"));

  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

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
    } catch {
      // Swallow errors: the screen must look identical whether or not the email
      // exists, mirroring the backend's anti-enumeration response.
      //
      // Unlike the other three forms, the widget is not reset here. The finally
      // below switches this page to its confirmation panel whatever happened, and
      // that unmounts the form and the widget with it, so there is no token left
      // to replace and nobody on this page to spend a fresh one.
    } finally {
      setIsLoading(false);
      setSubmitted(true);
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
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          label={t("forgotPassword.email")}
          type="email"
          autoComplete="email"
          placeholder={t("forgotPassword.emailPlaceholder")}
          error={errors.email}
          {...register("email")}
        />

        <TurnstileField action="password_reset" onToken={setTurnstileToken} />

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
