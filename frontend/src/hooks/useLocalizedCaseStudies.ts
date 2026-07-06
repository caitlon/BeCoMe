import { useTranslation } from "react-i18next";
import { caseStudies, CaseStudy } from "@/data/caseStudies";

// Localization swaps the text fields for translated strings at runtime; their
// types stay the same, so the CaseStudy union is reused as-is. An Omit-based
// interface would collapse the dataType/opinions discrimination.
export type LocalizedCaseStudy = CaseStudy;

export function useLocalizedCaseStudies(): LocalizedCaseStudy[] {
  const { t } = useTranslation("caseStudies");

  return caseStudies.map((study) => ({
    ...study,
    title: t(`${study.id}.title`),
    shortTitle: t(`${study.id}.shortTitle`),
    description: t(`${study.id}.description`),
    fullDescription: t(`${study.id}.fullDescription`),
    question: t(`${study.id}.question`),
    context: t(`${study.id}.context`),
    methodology: t(`${study.id}.methodology`),
    note: study.note ? t(`${study.id}.note`) : undefined,
    result: {
      ...study.result,
      interpretation: t(`${study.id}.interpretation`),
    },
  }));
}

export function useLocalizedCaseStudyById(id: string): LocalizedCaseStudy | undefined {
  const localizedStudies = useLocalizedCaseStudies();
  return localizedStudies.find((study) => study.id === id);
}

export function useLocalizedLikertLabel(value: number): string {
  const { t } = useTranslation("caseStudies");

  if (value <= 12.5) return t("likert.stronglyDisagree");
  if (value <= 37.5) return t("likert.ratherDisagree");
  if (value <= 62.5) return t("likert.neutral");
  if (value <= 87.5) return t("likert.ratherAgree");
  return t("likert.stronglyAgree");
}
