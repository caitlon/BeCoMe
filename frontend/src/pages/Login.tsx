import { useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import {
  FormField,
  PasswordInput,
  SubmitButton,
  TurnstileField,
  TurnstileFieldHandle,
} from "@/components/forms";
import { ResendVerification } from "@/components/auth/ResendVerification";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { useAuth } from "@/contexts/AuthContext";
import { useAuthSubmit } from "@/hooks/use-auth-submit";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { ForbiddenError, isTurnstileRefusal } from "@/lib/errors";
import { isTurnstileRequired } from "@/lib/turnstile";

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

  const turnstileRef = useRef<TurnstileFieldHandle>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const awaitingTurnstile = isTurnstileRequired() && turnstileToken === null;

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
      () => login(data.email, data.password, turnstileToken),
      (error) => {
        // The token was spent on the attempt that just failed. Without a fresh one
        // every retry on this page would be refused for a reason that has nothing
        // to do with the credentials the user is correcting.
        turnstileRef.current?.reset();
        // Two unrelated refusals answer 403 on this route, and only one of them is
        // about the account. A bot check refused while Cloudflare's siteverify is
        // unreachable refuses every sign-in, so claiming it here would tell every
        // user that their long-verified account is unconfirmed, and send them to a
        // resend flow that is guarded by the same check. Leave it to the toast,
        // which says the check did not go through and to try again; the widget has
        // just been reset, so there is a fresh challenge to try with.
        // These two lines cannot be swapped: a refused bot check is itself a
        // ForbiddenError, so the second test claims it as well and the order is
        // the only thing keeping them apart. A test covers this ordering.
        if (isTurnstileRefusal(error)) return false;
        if (!(error instanceof ForbiddenError)) return false;
        // Everything else 403 on this route is an unverified account, including a
        // 403 with no code at all, which is what an API deployed before the code
        // existed answers. Not a login failure to explain with the generic error
        // toast: it has its own recovery path (resend below), so claim the error
        // and render that instead.
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
      {/* eslint-disable-next-line react-hooks/refs -- handleSubmit defers to the browser's submit event; turnstileRef is only read/written once that event fires, never during render */}
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

        <TurnstileField action="login" ref={turnstileRef} onToken={setTurnstileToken} />

        <SubmitButton
          className="w-full"
          isLoading={isLoading}
          loadingText={t("login.signingIn")}
          disabled={awaitingTurnstile}
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
