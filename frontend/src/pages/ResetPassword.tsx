import { useId, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import {
  FormField,
  PasswordInput,
  SubmitButton,
  ValidationChecklist,
} from "@/components/forms";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { describeError } from "@/lib/errorMessages";
import { isRateLimited, isServiceUnavailable } from "@/lib/errors";
import { buildPasswordSchema, getPasswordRequirements } from "@/lib/validation";

type ResetPasswordFormData = {
  password: string;
  confirmPassword: string;
};

const ResetPassword = () => {
  const { t } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.resetPassword"));

  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const schema = useMemo(
    () =>
      z
        .object({
          password: buildPasswordSchema(t),
          confirmPassword: z.string().min(1, t("validation.passwordRequired")),
        })
        .refine((data) => data.password === data.confirmPassword, {
          error: t("validation.passwordsMatch"),
          path: ["confirmPassword"],
        }),
    [t]
  );

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isValid },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(schema),
    mode: "onTouched",
  });

  const password = useWatch({ control, name: "password", defaultValue: "" });
  const passwordRequirements = getPasswordRequirements(password, t);
  const passwordChecklistId = useId();
  const passwordChecklistShown = !!password && !passwordRequirements.every((req) => req.met);

  const onSubmit = async (data: ResetPasswordFormData) => {
    if (!token) return;
    setIsLoading(true);
    try {
      await api.resetPassword(token, data.password);
      toast({
        title: t("resetPassword.successTitle"),
        description: t("resetPassword.successMessage"),
      });
      // The server ended every session of this user; /login is a guest route and
      // would bounce a client that still reads as signed in.
      await refreshUser();
      navigate("/login");
    } catch (error) {
      // The API answers an invalid, expired or already used token with one opaque
      // 400, so only an outage or a throttled request is told apart from it. Blaming
      // the link for those sends the user off to request a new one for nothing.
      const description =
        isServiceUnavailable(error) || isRateLimited(error)
          ? describeError(error, tCommon, t("resetPassword.errorInvalidToken"))
          : t("resetPassword.errorInvalidToken");
      toast({
        title: t("resetPassword.errorTitle"),
        description,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <AuthLayout title={t("resetPassword.title")}>
        <p className="text-center text-sm text-muted-foreground">
          {t("resetPassword.missingToken")}
        </p>
        <p className="text-center text-sm text-muted-foreground mt-6">
          <Link
            to="/forgot-password"
            className="text-foreground hover:underline"
          >
            {t("resetPassword.requestNewLink")}
          </Link>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t("resetPassword.title")}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <PasswordInput
            label={t("resetPassword.password")}
            autoComplete="new-password"
            placeholder={t("resetPassword.passwordPlaceholder")}
            error={errors.password}
            aria-describedby={passwordChecklistShown ? passwordChecklistId : undefined}
            {...register("password")}
          />
          <ValidationChecklist
            id={passwordChecklistId}
            title={t("passwordRequirements.title")}
            requirements={passwordRequirements}
            show={passwordChecklistShown}
          />
        </div>

        <FormField
          label={t("resetPassword.confirmPassword")}
          type="password"
          autoComplete="new-password"
          placeholder={t("resetPassword.confirmPasswordPlaceholder")}
          error={errors.confirmPassword}
          aria-required="true"
          {...register("confirmPassword")}
        />

        <SubmitButton
          className="w-full"
          isLoading={isLoading}
          loadingText={t("resetPassword.submitting")}
          disabled={!isValid}
        >
          {t("resetPassword.submit")}
        </SubmitButton>
      </form>
    </AuthLayout>
  );
};

export default ResetPassword;
