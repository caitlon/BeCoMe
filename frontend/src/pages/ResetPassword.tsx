import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
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
import { api } from "@/lib/api";
import { SPECIAL_CHAR_REGEX, getPasswordRequirements } from "@/lib/validation";

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
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const schema = useMemo(
    () =>
      z
        .object({
          password: z
            .string()
            .min(12, t("passwordRequirements.minLength"))
            .max(128, t("validation.passwordMaxLength"))
            .regex(/[A-Z]/, t("passwordRequirements.uppercase"))
            .regex(/[a-z]/, t("passwordRequirements.lowercase"))
            .regex(/\d/, t("passwordRequirements.number"))
            .regex(SPECIAL_CHAR_REGEX, t("passwordRequirements.specialChar")),
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

  const onSubmit = async (data: ResetPasswordFormData) => {
    if (!token) return;
    setIsLoading(true);
    try {
      await api.resetPassword(token, data.password);
      toast({
        title: t("resetPassword.successTitle"),
        description: t("resetPassword.successMessage"),
      });
      navigate("/login");
    } catch {
      toast({
        title: t("resetPassword.errorTitle"),
        description: t("resetPassword.errorInvalidToken"),
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
            placeholder={t("resetPassword.passwordPlaceholder")}
            error={errors.password}
            {...register("password")}
          />
          <ValidationChecklist
            title={t("passwordRequirements.title")}
            requirements={passwordRequirements}
            show={!!password}
          />
        </div>

        <FormField
          label={t("resetPassword.confirmPassword")}
          type="password"
          placeholder={t("resetPassword.confirmPasswordPlaceholder")}
          error={errors.confirmPassword}
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
