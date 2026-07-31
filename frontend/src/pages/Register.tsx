import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import {
  FormField,
  PasswordInput,
  SubmitButton,
  ValidationChecklist,
  Requirement,
} from "@/components/forms";
import { ResendVerification } from "@/components/auth/ResendVerification";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { describeError } from "@/lib/errorMessages";
import { buildPasswordSchema, getPasswordRequirements } from "@/lib/validation";

type RegisterFormData = {
  email: string;
  password: string;
  confirmPassword: string;
  firstName: string;
  lastName: string;
};

const getEmailRequirements = (
  email: string,
  t: (key: string) => string
): Requirement[] => [
  {
    label: t("emailRequirements.hasAt"),
    met: email.includes("@"),
  },
  {
    label: t("emailRequirements.hasDomain"),
    met: /@.+\..+/.test(email),
  },
  {
    label: t("emailRequirements.noSpaces"),
    met: !email.includes(" "),
  },
];

const Register = () => {
  const { t } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.register"));
  const { toast } = useToast();

  const [isLoading, setIsLoading] = useState(false);
  // Carries the address and password the user just typed into the
  // check-your-inbox state, so the resend control there can call
  // api.resendVerification without asking the user to type the password
  // again -- kept only in this component's state, never persisted.
  const [submitted, setSubmitted] = useState<{ email: string; password: string } | null>(
    null
  );

  const registerSchema = useMemo(
    () =>
      z
        .object({
          email: z
            .email(t("validation.emailInvalid"))
            .max(255, t("validation.emailMaxLength"))
            .refine((val) => /^[\x20-\x7E]*$/.test(val), {
              error: t("validation.emailAsciiOnly"),
            }),
          password: buildPasswordSchema(t),
          confirmPassword: z.string().min(1, t("validation.passwordRequired")),
          firstName: z
            .string()
            .min(1, t("validation.firstNameRequired"))
            .max(100)
            .regex(/^[\p{L}\s'-]+$/u, t("validation.nameFormat")),
          lastName: z
            .string()
            .min(1, t("validation.lastNameRequired"))
            .max(100)
            .regex(/^[\p{L}\s'-]+$/u, t("validation.nameFormat")),
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
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    mode: "onTouched",
  });

  const email = useWatch({ control, name: "email", defaultValue: "" });
  const password = useWatch({ control, name: "password", defaultValue: "" });
  const emailRequirements = getEmailRequirements(email, t);
  const passwordRequirements = getPasswordRequirements(password, t);

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true);
    try {
      await api.register({
        email: data.email,
        password: data.password,
        first_name: data.firstName,
        last_name: data.lastName,
      });
      // 202 identically for a free, unverified, or already-verified address --
      // the "check your inbox" state is the whole flow's success state, there
      // is no user object and no session to move to /projects with.
      setSubmitted({ email: data.email, password: data.password });
    } catch (error) {
      toast({
        title: t("register.errorTitle"),
        description: describeError(error, tCommon, t("register.errorMessage")),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (submitted) {
    return (
      <AuthLayout title={t("register.checkInboxTitle")}>
        <p className="text-center text-sm text-muted-foreground">
          {t("register.checkInboxMessage", { email: submitted.email })}
        </p>
        <div className="mt-6">
          <ResendVerification email={submitted.email} password={submitted.password} />
        </div>
        <p className="text-center text-sm text-muted-foreground mt-6">
          <Link to="/login" className="text-foreground hover:underline">
            {t("register.backToLogin")}
          </Link>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t("register.title")}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <FormField
            label={`${t("register.email")} *`}
            type="email"
            autoComplete="email"
            placeholder={t("register.emailPlaceholder")}
            error={errors.email}
            {...register("email")}
          />
          <ValidationChecklist
            title={t("emailRequirements.title")}
            requirements={emailRequirements}
            show={!!email}
          />
        </div>

        <div>
          <PasswordInput
            label={`${t("register.password")} *`}
            autoComplete="new-password"
            placeholder={t("register.passwordPlaceholder")}
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
          label={`${t("register.confirmPassword")} *`}
          type="password"
          autoComplete="new-password"
          placeholder={t("register.confirmPasswordPlaceholder")}
          error={errors.confirmPassword}
          {...register("confirmPassword")}
        />

        <FormField
          label={`${t("register.firstName")} *`}
          autoComplete="given-name"
          placeholder={t("register.firstNamePlaceholder")}
          error={errors.firstName}
          {...register("firstName")}
        />

        <FormField
          label={`${t("register.lastName")} *`}
          autoComplete="family-name"
          placeholder={t("register.lastNamePlaceholder")}
          error={errors.lastName}
          {...register("lastName")}
        />

        <SubmitButton
          className="w-full"
          isLoading={isLoading}
          loadingText={t("register.creatingAccount")}
          disabled={!isValid}
        >
          {t("register.createAccount")}
        </SubmitButton>
      </form>

      <p className="text-center text-sm text-muted-foreground mt-6">
        {t("register.haveAccount")}{" "}
        <Link to="/login" className="text-foreground hover:underline">
          {t("register.signIn")}
        </Link>
      </p>
    </AuthLayout>
  );
};

export default Register;
