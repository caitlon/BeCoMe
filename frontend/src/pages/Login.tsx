import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import { FormField, PasswordInput, SubmitButton } from "@/components/forms";
import { ResendVerification } from "@/components/auth/ResendVerification";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useAuth } from "@/contexts/AuthContext";
import { useAuthSubmit } from "@/hooks/use-auth-submit";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { ForbiddenError } from "@/lib/errors";

type LoginFormData = {
  email: string;
  password: string;
};

const Login = () => {
  const { t } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  const { login } = useAuth();
  useDocumentTitle(tCommon("pageTitle.login"));

  // Set on a 403 (account not verified yet); carries the credentials the user
  // just typed so the resend control below does not have to ask again.
  const [notVerified, setNotVerified] = useState<{ email: string; password: string } | null>(
    null
  );

  const { isLoading, execute } = useAuthSubmit({
    successTitle: t("login.successTitle"),
    successDescription: t("login.successMessage"),
    errorTitle: t("login.errorTitle"),
    errorFallback: t("login.errorMessage"),
  });

  const loginSchema = useMemo(
    () =>
      z.object({
        email: z.email(t("validation.emailInvalid")),
        password: z.string().min(1, t("validation.passwordRequired")),
      }),
    [t]
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    mode: "onTouched",
  });

  const onSubmit = (data: LoginFormData) =>
    execute(
      () => login(data.email, data.password),
      (error) => {
        if (!(error instanceof ForbiddenError)) return false;
        // An unverified account is not a login failure to explain with the
        // generic error toast: it has its own recovery path (resend below),
        // so claim the error and render that instead.
        setNotVerified({ email: data.email, password: data.password });
        return true;
      }
    );

  if (notVerified) {
    return (
      <AuthLayout title={t("login.notVerifiedTitle")}>
        <p className="text-center text-sm text-muted-foreground">
          {t("login.notVerifiedMessage")}
        </p>
        <div className="mt-6">
          <ResendVerification email={notVerified.email} password={notVerified.password} />
        </div>
        <p className="text-center text-sm mt-6">
          <button
            type="button"
            className="text-foreground hover:underline"
            onClick={() => setNotVerified(null)}
          >
            {t("login.backToSignIn")}
          </button>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t("login.title")}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          label={t("login.email")}
          type="email"
          autoComplete="email"
          placeholder={t("login.emailPlaceholder")}
          error={errors.email}
          {...register("email")}
        />

        <PasswordInput
          label={t("login.password")}
          autoComplete="current-password"
          placeholder={t("login.passwordPlaceholder")}
          error={errors.password}
          {...register("password")}
        />

        <div className="text-right -mt-2">
          <Link
            to="/forgot-password"
            className="text-sm text-muted-foreground hover:underline"
          >
            {t("login.forgotPassword")}
          </Link>
        </div>

        <SubmitButton
          className="w-full"
          isLoading={isLoading}
          loadingText={t("login.signingIn")}
        >
          {t("login.signIn")}
        </SubmitButton>
      </form>

      <p className="text-center text-sm text-muted-foreground mt-6">
        {t("login.noAccount")}{" "}
        <Link to="/register" className="text-foreground hover:underline">
          {t("login.createOne")}
        </Link>
      </p>
    </AuthLayout>
  );
};

export default Login;
