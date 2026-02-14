import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
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
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { SPECIAL_CHAR_REGEX, getPasswordRequirements } from "@/lib/validation";

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
  const navigate = useNavigate();
  const { register: registerUser } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  useDocumentTitle(tCommon("pageTitle.register"));

  const registerSchema = useMemo(
    () =>
      z
        .object({
          email: z
            .string()
            .email(t("validation.emailInvalid"))
            .max(255, t("validation.emailMaxLength"))
            .refine((val) => /^[\x20-\x7E]*$/.test(val), {
              message: t("validation.emailAsciiOnly"),
            }),
          password: z
            .string()
            .min(12, t("passwordRequirements.minLength"))
            .max(128, t("validation.passwordMaxLength"))
            .regex(/[A-Z]/, t("passwordRequirements.uppercase"))
            .regex(/[a-z]/, t("passwordRequirements.lowercase"))
            .regex(/\d/, t("passwordRequirements.number"))
            .regex(SPECIAL_CHAR_REGEX, t("passwordRequirements.specialChar")),
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
          message: t("validation.passwordsMatch"),
          path: ["confirmPassword"],
        }),
    [t]
  );

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isValid },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    mode: "onTouched",
  });

  const email = watch("email", "");
  const password = watch("password", "");
  const emailRequirements = getEmailRequirements(email, t);
  const passwordRequirements = getPasswordRequirements(password, t);

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true);
    try {
      await registerUser(
        data.email,
        data.password,
        data.firstName,
        data.lastName
      );
      toast({
        title: t("register.successTitle"),
        description: t("register.successMessage"),
      });
      navigate("/projects");
    } catch (error) {
      toast({
        title: t("register.errorTitle"),
        description:
          error instanceof Error ? error.message : t("register.errorMessage"),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout title={t("register.title")}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <FormField
            label={`${t("register.email")} *`}
            type="email"
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
          placeholder={t("register.confirmPasswordPlaceholder")}
          error={errors.confirmPassword}
          {...register("confirmPassword")}
        />

        <FormField
          label={`${t("register.firstName")} *`}
          placeholder={t("register.firstNamePlaceholder")}
          error={errors.firstName}
          {...register("firstName")}
        />

        <FormField
          label={`${t("register.lastName")} *`}
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
