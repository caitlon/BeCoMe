import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import { PasswordInput, SubmitButton } from "@/components/forms";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { describeError } from "@/lib/errorMessages";
import { ForbiddenError, HttpError, isRateLimited } from "@/lib/errors";

type VerifyEmailFormData = {
  password: string;
};

// The three failure modes the backend distinguishes for this endpoint, each
// needing its own recovery (see api/routes/auth.py:verify_email): a wrong
// password keeps the link and form so the user can retry; an unusable link
// (unknown, expired, already used, or already verified) cannot succeed on
// retry, so the form is replaced; a lockout is temporary, so the form stays.
type VerifyFailure = "wrongPassword" | "invalidLink" | "lockedOut";

const VerifyEmail = () => {
  const { t, i18n } = useTranslation("auth");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.verifyEmail"));

  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [failure, setFailure] = useState<VerifyFailure | null>(null);

  const schema = useMemo(
    () =>
      z.object({
        password: z.string().min(1, t("validation.passwordRequired")),
      }),
    [t]
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<VerifyEmailFormData>({
    resolver: zodResolver(schema),
    mode: "onTouched",
  });

  const onSubmit = async (data: VerifyEmailFormData) => {
    /* v8 ignore next -- defensive fallback: the form (and so this handler)
       only renders once the missing-token early return below has already
       ruled out a null token */
    if (!token) return;
    setIsLoading(true);
    setFailure(null);
    try {
      // i18next has no supportedLngs allowlist, so i18n.language can be any
      // browser-reported locale (e.g. "de-DE"), not just one we have
      // resources for. The backend only accepts "en" or "cs"
      // (Literal["en", "cs"]), so this clamps to those two instead of
      // forwarding a raw slice that a third language would fail on. Same
      // clamp as ResultExportMenu's handleExport.
      const language = i18n.language.startsWith("cs") ? "cs" : "en";
      await api.verifyEmail(token, data.password, language);
      toast({
        title: t("verifyEmail.successTitle"),
        description: t("verifyEmail.successMessage"),
      });
      navigate("/login");
    } catch (error) {
      if (error instanceof ForbiddenError) {
        setFailure("wrongPassword");
      } else if (isRateLimited(error)) {
        setFailure("lockedOut");
      } else if (error instanceof HttpError && error.status === 400) {
        setFailure("invalidLink");
      } else {
        toast({
          title: t("verifyEmail.errorTitle"),
          description: describeError(error, tCommon, t("verifyEmail.errorMessage")),
          variant: "destructive",
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <AuthLayout title={t("verifyEmail.title")}>
        <p className="text-center text-sm text-muted-foreground">
          {t("verifyEmail.missingToken")}
        </p>
        <p className="text-center text-sm text-muted-foreground mt-6">
          <Link to="/login" className="text-foreground hover:underline">
            {t("verifyEmail.goToLogin")}
          </Link>
        </p>
      </AuthLayout>
    );
  }

  if (failure === "invalidLink") {
    return (
      <AuthLayout title={t("verifyEmail.title")}>
        <p role="alert" className="text-center text-sm text-destructive">
          {t("verifyEmail.invalidLink")}
        </p>
        <p className="text-center text-sm text-muted-foreground mt-6">
          <Link to="/login" className="text-foreground hover:underline">
            {t("verifyEmail.goToLogin")}
          </Link>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t("verifyEmail.title")}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <PasswordInput
          label={t("verifyEmail.password")}
          autoComplete="current-password"
          placeholder={t("verifyEmail.passwordPlaceholder")}
          error={errors.password}
          {...register("password")}
        />

        {failure === "wrongPassword" && (
          <p role="alert" className="text-sm text-destructive">
            {t("verifyEmail.wrongPassword")}
          </p>
        )}
        {failure === "lockedOut" && (
          <p role="alert" className="text-sm text-destructive">
            {t("verifyEmail.lockedOut")}
          </p>
        )}

        {/* The lockout state deliberately leaves the button enabled: it is the one
            failure the user recovers from by doing exactly what the message says,
            and disabling the control would leave a page reload as the only way
            back. An early retry just gets another 429, which costs nothing. */}
        <SubmitButton
          className="w-full"
          isLoading={isLoading}
          loadingText={t("verifyEmail.submitting")}
        >
          {t("verifyEmail.submit")}
        </SubmitButton>
      </form>
    </AuthLayout>
  );
};

export default VerifyEmail;
