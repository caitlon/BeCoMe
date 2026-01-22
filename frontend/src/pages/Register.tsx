import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Eye, EyeOff, Loader2, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Navbar } from "@/components/layout/Navbar";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";

type RegisterFormData = {
  email: string;
  password: string;
  confirmPassword: string;
  firstName: string;
  lastName?: string;
};

type ValidationRequirement = {
  key: string;
  label: string;
  met: boolean;
};

const getEmailRequirements = (
  email: string,
  t: (key: string) => string
): ValidationRequirement[] => [
  {
    key: "hasAt",
    label: t("emailRequirements.hasAt"),
    met: email.includes("@"),
  },
  {
    key: "hasDomain",
    label: t("emailRequirements.hasDomain"),
    met: /@.+\..+/.test(email),
  },
  {
    key: "noSpaces",
    label: t("emailRequirements.noSpaces"),
    met: !email.includes(" "),
  },
];

const getPasswordRequirements = (
  password: string,
  t: (key: string) => string
): ValidationRequirement[] => [
  {
    key: "minLength",
    label: t("passwordRequirements.minLength"),
    met: password.length >= 8,
  },
  {
    key: "uppercase",
    label: t("passwordRequirements.uppercase"),
    met: /[A-Z]/.test(password),
  },
  {
    key: "lowercase",
    label: t("passwordRequirements.lowercase"),
    met: /[a-z]/.test(password),
  },
  {
    key: "number",
    label: t("passwordRequirements.number"),
    met: /\d/.test(password),
  },
];

const Register = () => {
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const { register: registerUser } = useAuth();
  const { toast } = useToast();
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const registerSchema = useMemo(
    () =>
      z
        .object({
          email: z
            .string()
            .email(t("validation.emailInvalid"))
            .max(255, t("validation.emailMaxLength")),
          password: z
            .string()
            .min(8, t("passwordRequirements.minLength"))
            .max(128, t("validation.passwordMaxLength"))
            .regex(/[A-Z]/, t("passwordRequirements.uppercase"))
            .regex(/[a-z]/, t("passwordRequirements.lowercase"))
            .regex(/\d/, t("passwordRequirements.number")),
          confirmPassword: z.string().min(1, t("validation.passwordRequired")),
          firstName: z
            .string()
            .min(1, t("validation.firstNameRequired"))
            .max(100)
            .regex(/^[\p{L}\s'-]+$/u, t("validation.nameFormat")),
          lastName: z
            .string()
            .max(100)
            .regex(/^[\p{L}\s'-]*$/u, t("validation.nameFormat"))
            .optional(),
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
  const allEmailRequirementsMet = emailRequirements.every((req) => req.met);
  const allPasswordRequirementsMet = passwordRequirements.every((req) => req.met);

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
        description: error instanceof Error ? error.message : t("register.errorMessage"),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <div className="flex-1 flex items-center justify-center py-12 px-6">
        <motion.div
          className="w-full max-w-md"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card className="border-border/50">
            <CardHeader className="text-center pb-2">
              <CardTitle className="font-display text-2xl font-normal">
                {t("register.title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">{t("register.email")} *</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder={t("register.emailPlaceholder")}
                    {...register("email")}
                    className={errors.email ? "border-destructive" : ""}
                  />
                  {email && !allEmailRequirementsMet && (
                    <div className="mt-3 space-y-1.5">
                      <p className="text-xs text-muted-foreground font-medium">
                        {t("emailRequirements.title")}
                      </p>
                      {emailRequirements.map((req) => (
                        <div
                          key={req.key}
                          className={`flex items-center gap-2 text-xs ${
                            req.met ? "text-success" : "text-muted-foreground"
                          }`}
                        >
                          {req.met ? (
                            <Check className="h-3.5 w-3.5" />
                          ) : (
                            <X className="h-3.5 w-3.5" />
                          )}
                          <span>{req.label}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">{t("register.password")} *</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      placeholder={t("register.passwordPlaceholder")}
                      {...register("password")}
                      className={
                        errors.password ? "border-destructive pr-10" : "pr-10"
                      }
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  {password && !allPasswordRequirementsMet && (
                    <div className="mt-3 space-y-1.5">
                      <p className="text-xs text-muted-foreground font-medium">
                        {t("passwordRequirements.title")}
                      </p>
                      {passwordRequirements.map((req) => (
                        <div
                          key={req.key}
                          className={`flex items-center gap-2 text-xs ${
                            req.met ? "text-success" : "text-muted-foreground"
                          }`}
                        >
                          {req.met ? (
                            <Check className="h-3.5 w-3.5" />
                          ) : (
                            <X className="h-3.5 w-3.5" />
                          )}
                          <span>{req.label}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {errors.password && (
                    <p className="text-sm text-destructive">
                      {errors.password.message}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">
                    {t("register.confirmPassword")} *
                  </Label>
                  <Input
                    id="confirmPassword"
                    type="password"
                    placeholder={t("register.confirmPasswordPlaceholder")}
                    {...register("confirmPassword")}
                    className={errors.confirmPassword ? "border-destructive" : ""}
                  />
                  {errors.confirmPassword && (
                    <p className="text-sm text-destructive">
                      {errors.confirmPassword.message}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="firstName">{t("register.firstName")} *</Label>
                  <Input
                    id="firstName"
                    placeholder={t("register.firstNamePlaceholder")}
                    {...register("firstName")}
                    className={errors.firstName ? "border-destructive" : ""}
                  />
                  {errors.firstName && (
                    <p className="text-sm text-destructive">
                      {errors.firstName.message}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="lastName">{t("register.lastName")}</Label>
                  <Input
                    id="lastName"
                    placeholder={t("register.lastNamePlaceholder")}
                    {...register("lastName")}
                  />
                </div>

                <Button type="submit" className="w-full" disabled={!isValid || isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t("register.creatingAccount")}
                    </>
                  ) : (
                    t("register.createAccount")
                  )}
                </Button>
              </form>

              <p className="text-center text-sm text-muted-foreground mt-6">
                {t("register.haveAccount")}{" "}
                <Link to="/login" className="text-foreground hover:underline">
                  {t("register.signIn")}
                </Link>
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
};

export default Register;
