import { z } from "zod";

import { Requirement } from "@/components/forms";

export const SPECIAL_CHAR_REGEX = /[!@#$%^&*(),.?":{}|<>\-_=+[\]\\;'/`~]/;

export const PASSWORD_MIN_LENGTH = 12;
export const PASSWORD_MAX_LENGTH = 128;

/**
 * Single source of truth for the password policy. Both the live requirement
 * checklist and the zod schemas are derived from this list, so the rules can
 * never drift apart.
 */
const PASSWORD_RULES = [
  {
    i18nKey: "passwordRequirements.minLength",
    test: (password: string) => password.length >= PASSWORD_MIN_LENGTH,
  },
  {
    i18nKey: "passwordRequirements.uppercase",
    test: (password: string) => /[A-Z]/.test(password),
  },
  {
    i18nKey: "passwordRequirements.lowercase",
    test: (password: string) => /[a-z]/.test(password),
  },
  {
    i18nKey: "passwordRequirements.number",
    test: (password: string) => /\d/.test(password),
  },
  {
    i18nKey: "passwordRequirements.specialChar",
    test: (password: string) => SPECIAL_CHAR_REGEX.test(password),
  },
] as const;

export const getPasswordRequirements = (
  password: string,
  t: (key: string) => string
): Requirement[] =>
  PASSWORD_RULES.map((rule) => ({
    label: t(rule.i18nKey),
    met: rule.test(password),
  }));

export const buildPasswordSchema = (t: (key: string) => string): z.ZodType<string, string> =>
  PASSWORD_RULES.reduce<z.ZodType<string, string>>(
    (schema, rule) => schema.refine(rule.test, { error: t(rule.i18nKey) }),
    z.string().max(PASSWORD_MAX_LENGTH, t("validation.passwordMaxLength"))
  );
