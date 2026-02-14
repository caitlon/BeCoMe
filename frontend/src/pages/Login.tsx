import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import { FormField, PasswordInput, SubmitButton } from "@/components/forms";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useAuth } from "@/contexts/AuthContext";
import { useAuthSubmit } from "@/hooks/use-auth-submit";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

type LoginFormData = {
  email: string;
  password: string;
};

const Login = () => {
  const { t } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  const { login } = useAuth();
  useDocumentTitle(tCommon("pageTitle.login"));

  const { isLoading, execute } = useAuthSubmit({
    successTitle: t("login.successTitle"),
    successDescription: t("login.successMessage"),
    errorTitle: t("login.errorTitle"),
    errorFallback: t("login.errorMessage"),
  });

  const loginSchema = useMemo(
    () =>
      z.object({
        email: z.string().email(t("validation.emailInvalid")),
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
    execute(() => login(data.email, data.password));

  return (
    <AuthLayout title={t("login.title")}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          label={t("login.email")}
          type="email"
          placeholder={t("login.emailPlaceholder")}
          error={errors.email}
          {...register("email")}
        />

        <PasswordInput
          label={t("login.password")}
          placeholder={t("login.passwordPlaceholder")}
          error={errors.password}
          {...register("password")}
        />

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
