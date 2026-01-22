import { useTranslation } from "react-i18next";
import { caseStudies, CaseStudy } from "@/data/caseStudies";

export interface LocalizedCaseStudy extends Omit<CaseStudy, "title" | "shortTitle" | "description" | "fullDescription" | "question" | "context" | "methodology" | "note" | "result"> {
  title: string;
  shortTitle: string;
  description: string;
  fullDescription: string;
  question: string;
  context: string;
  methodology: string;
  note?: string;
  result: {
    bestCompromise: number;
    maxError: number;
    interpretation: string;
  };
}

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
