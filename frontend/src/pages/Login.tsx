import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormField, PasswordInput, SubmitButton } from "@/components/forms";
import { Navbar } from "@/components/layout/Navbar";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

type LoginFormData = {
  email: string;
  password: string;
};

const Login = () => {
  const { t } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  useDocumentTitle(tCommon("pageTitle.login"));

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

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    try {
      await login(data.email, data.password);
      toast({
        title: t("login.successTitle"),
        description: t("login.successMessage"),
      });
      navigate("/projects");
    } catch (error) {
      toast({
        title: t("login.errorTitle"),
        description:
          error instanceof Error ? error.message : t("login.errorMessage"),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main id="main-content" className="flex-1 flex items-center justify-center py-12 px-6">
        <motion.div
          className="w-full max-w-md"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card className="border-border/50">
            <CardHeader className="text-center pb-2">
              <CardTitle as="h1" className="font-display text-2xl font-normal">
                {t("login.title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
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

                <div className="text-right">
                  <button
                    type="button"
                    className="text-sm text-muted-foreground hover:text-foreground hover:underline"
                  >
                    {t("login.forgotPassword")}
                  </button>
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
            </CardContent>
          </Card>
        </motion.div>
      </main>
    </div>
  );
};

export default Login;
