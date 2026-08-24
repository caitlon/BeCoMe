import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import enCommon from "./locales/en/common.json";
import enLanding from "./locales/en/landing.json";
import enAuth from "./locales/en/auth.json";
import enAbout from "./locales/en/about.json";
import enProjects from "./locales/en/projects.json";
import enProfile from "./locales/en/profile.json";
import enCaseStudies from "./locales/en/caseStudies.json";
import enDocs from "./locales/en/docs.json";
import enOnboarding from "./locales/en/onboarding.json";
import enFaq from "./locales/en/faq.json";

import csCommon from "./locales/cs/common.json";
import csLanding from "./locales/cs/landing.json";
import csAuth from "./locales/cs/auth.json";
import csAbout from "./locales/cs/about.json";
import csProjects from "./locales/cs/projects.json";
import csProfile from "./locales/cs/profile.json";
import csCaseStudies from "./locales/cs/caseStudies.json";
import csDocs from "./locales/cs/docs.json";
import csOnboarding from "./locales/cs/onboarding.json";
import csFaq from "./locales/cs/faq.json";

export const defaultNS = "common";

export const resources = {
  en: {
    common: enCommon,
    landing: enLanding,
    auth: enAuth,
    about: enAbout,
    projects: enProjects,
    profile: enProfile,
    caseStudies: enCaseStudies,
    docs: enDocs,
    onboarding: enOnboarding,
    faq: enFaq,
  },
  cs: {
    common: csCommon,
    landing: csLanding,
    auth: csAuth,
    about: csAbout,
    projects: csProjects,
    profile: csProfile,
    caseStudies: csCaseStudies,
    docs: csDocs,
    onboarding: csOnboarding,
    faq: csFaq,
  },
} as const;

// The two languages resources exist for, and the only two the backend accepts
// (Literal["en", "cs"] in api/schemas/auth.py and friends).
export type SupportedLanguage = "en" | "cs";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en",
    defaultNS,
    resources,
    // Without this, i18n.language can resolve to any code the browser reports --
    // "de-DE", "fr-CA" -- and i18next will happily leave it there instead of
    // narrowing to a language resources actually exist for.
    supportedLngs: ["en", "cs"],
    // supportedLngs alone is not enough for a regional tag: i18next first scans
    // the browser's full list of reported languages for an exact match against
    // supportedLngs before it ever tries reducing anything, so a detected list
    // like ["cs-CZ", "en"] matches "en" and drops Czech entirely, never reaching
    // the fallback step that would have reduced "cs-CZ" to "cs". This option makes
    // the exact-match pass itself accept a regional tag whose language part is
    // supported, so "cs-CZ" matches (and its resources load) without waiting for
    // a plainer candidate to win by being listed with no region at all. Verified
    // against the installed i18next 26.3.6 + i18next-browser-languagedetector
    // 8.2.1: even with this on, i18next can still resolve i18n.language itself to
    // the untrimmed regional tag rather than the bare language -- toSupportedLanguage
    // below is what turns whatever it lands on into the exact literal the backend
    // contract requires; this option is what keeps Czech from being discarded
    // before that helper ever runs.
    nonExplicitSupportedLngs: true,
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "become-language",
    },
    interpolation: {
      escapeValue: false,
    },
  });

/**
 * Reduce an i18next language tag to the literal the backend accepts.
 *
 * i18n.language can still carry a region ("cs-CZ") or, briefly during startup or
 * for a visitor whose browser reports a third language entirely, something
 * outside {@link SupportedLanguage}. This is the one place that narrows it to
 * "en" or "cs" for every caller that has to send a language to the backend
 * (activation, result export) -- keep it explicit rather than trusting init's
 * supportedLngs alone, since only a typed return value makes that contract
 * checkable at the call site.
 *
 * @param language - Usually `i18n.language`.
 * @returns "cs" for any Czech-family tag, "en" otherwise.
 */
export function toSupportedLanguage(language: string): SupportedLanguage {
  return language.startsWith("cs") ? "cs" : "en";
}

// Update HTML lang attribute for screen readers
i18n.on("languageChanged", (lng) => {
  /* v8 ignore next */
  if (typeof document !== "undefined") {
    document.documentElement.lang = lng;
  }
});
/* v8 ignore next */
if (typeof document !== "undefined") {
  document.documentElement.lang = i18n.language;
}

export default i18n;
