import { Requirement } from "@/components/forms";

export const SPECIAL_CHAR_REGEX = /[!@#$%^&*(),.?":{}|<>\-_=+[\]\\;'/`~]/;

export const getPasswordRequirements = (
  password: string,
  t: (key: string) => string
): Requirement[] => [
  {
    label: t("passwordRequirements.minLength"),
    met: password.length >= 12,
  },
  {
    label: t("passwordRequirements.uppercase"),
    met: /[A-Z]/.test(password),
  },
  {
    label: t("passwordRequirements.lowercase"),
    met: /[a-z]/.test(password),
  },
  {
    label: t("passwordRequirements.number"),
    met: /\d/.test(password),
  },
  {
    label: t("passwordRequirements.specialChar"),
    met: SPECIAL_CHAR_REGEX.test(password),
  },
];
