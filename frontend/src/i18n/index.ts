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

import csCommon from "./locales/cs/common.json";
import csLanding from "./locales/cs/landing.json";
import csAuth from "./locales/cs/auth.json";
import csAbout from "./locales/cs/about.json";
import csProjects from "./locales/cs/projects.json";
import csProfile from "./locales/cs/profile.json";
import csCaseStudies from "./locales/cs/caseStudies.json";
import csDocs from "./locales/cs/docs.json";
import csOnboarding from "./locales/cs/onboarding.json";

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
  },
} as const;

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en",
    defaultNS,
    resources,
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "become-language",
    },
    interpolation: {
      escapeValue: false,
    },
  });

// Update HTML lang attribute for screen readers
i18n.on("languageChanged", (lng) => {
  if (typeof document !== "undefined") {
    document.documentElement.lang = lng;
  }
});
if (typeof document !== "undefined") {
  document.documentElement.lang = i18n.language;
}

export default i18n;
