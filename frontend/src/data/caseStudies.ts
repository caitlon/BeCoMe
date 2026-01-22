import { FileText, Droplets, Globe, LucideIcon } from "lucide-react";

export interface ExpertOpinion {
  role: string;
  bestProposal: number;
  lowerLimit: number;
  upperLimit: number;
}

export interface LikertOpinion {
  role: string;
  value: number;
}

export interface CaseStudy {
  id: string;
  title: string;
  shortTitle: string;
  description: string;
  fullDescription: string;
  question: string;
  icon: LucideIcon;
  experts: number;
  dataType: "interval" | "likert";
  scaleMin: number;
  scaleMax: number;
  scaleUnit: string;
  context: string;
  methodology: string;
  opinions: ExpertOpinion[] | LikertOpinion[];
  result: {
    bestCompromise: number;
    maxError: number;
    interpretation: string;
  };
  note?: string;
}

export const caseStudies: CaseStudy[] = [
  {
    id: "budget",
    title: "COVID-19 Budget Support",
    shortTitle: "Budget",
    description: "Budget allocation for pandemic response measures",
    fullDescription: "During the COVID-19 pandemic, the Czech government needed to determine the optimal financial support for entrepreneurs affected by restrictive measures. A panel of 22 high-ranking government officials from various ministries was assembled to provide their expert opinions.",
    question: "Based on the submitted analyses of the Ministry of Industry and Trade and the Czech National Bank on the impact of the measures on the state budget of the Czech Republic, propose the total financial support in the range CZK 0–100 billion for entrepreneurs affected by the COVID-19 pandemic.",
    icon: FileText,
    experts: 22,
    dataType: "interval",
    scaleMin: 0,
    scaleMax: 100,
    scaleUnit: "CZK billion",
    context: "The COVID-19 pandemic created unprecedented economic challenges. Businesses across sectors faced closures and reduced revenue due to government-mandated restrictions. The government needed to balance fiscal responsibility with the urgent need to support affected entrepreneurs and maintain economic stability.",
    methodology: "Each expert provided their opinion as a fuzzy triangular number with three values: best proposal (most likely value), lower limit (pessimistic estimate), and upper limit (optimistic estimate). The BeCoMe method aggregated these opinions to find the best compromise.",
    opinions: [
      { role: "Chairman", bestProposal: 70, lowerLimit: 40, upperLimit: 90 },
      { role: "Deputy Chairman", bestProposal: 80, lowerLimit: 60, upperLimit: 90 },
      { role: "Deputy Minister of Interior", bestProposal: 90, lowerLimit: 60, upperLimit: 90 },
      { role: "Deputy Minister of Defence", bestProposal: 40, lowerLimit: 30, upperLimit: 40 },
      { role: "Deputy Minister of Foreign Affairs", bestProposal: 70, lowerLimit: 40, upperLimit: 90 },
      { role: "Deputy Minister of Finance", bestProposal: 45, lowerLimit: 30, upperLimit: 70 },
      { role: "Deputy Minister of Health", bestProposal: 60, lowerLimit: 40, upperLimit: 85 },
      { role: "Deputy Minister of Industry and Trade", bestProposal: 90, lowerLimit: 40, upperLimit: 90 },
      { role: "Deputy Minister of Transport", bestProposal: 50, lowerLimit: 40, upperLimit: 50 },
      { role: "Deputy Minister of Education", bestProposal: 40, lowerLimit: 15, upperLimit: 60 },
      { role: "Deputy Minister of Agriculture", bestProposal: 50, lowerLimit: 40, upperLimit: 70 },
      { role: "Deputy Minister of Labour", bestProposal: 50, lowerLimit: 10, upperLimit: 50 },
      { role: "Deputy Minister of Culture", bestProposal: 30, lowerLimit: 10, upperLimit: 40 },
      { role: "Deputy Minister of Justice", bestProposal: 40, lowerLimit: 10, upperLimit: 50 },
      { role: "Chairman of SSHR", bestProposal: 40, lowerLimit: 40, upperLimit: 40 },
      { role: "Police President", bestProposal: 50, lowerLimit: 50, upperLimit: 50 },
      { role: "Chief Hygienist", bestProposal: 65, lowerLimit: 45, upperLimit: 80 },
      { role: "Economic Advisor 1", bestProposal: 55, lowerLimit: 35, upperLimit: 75 },
      { role: "Economic Advisor 2", bestProposal: 60, lowerLimit: 40, upperLimit: 80 },
      { role: "Regional Governor 1", bestProposal: 75, lowerLimit: 50, upperLimit: 85 },
      { role: "Regional Governor 2", bestProposal: 70, lowerLimit: 45, upperLimit: 90 },
      { role: "Business Association Rep", bestProposal: 85, lowerLimit: 60, upperLimit: 95 },
    ] as ExpertOpinion[],
    result: {
      bestCompromise: 57.3,
      maxError: 8.2,
      interpretation: "The best compromise suggests financial support of approximately 57.3 billion CZK, with a maximum estimation error of 8.2 billion CZK. This represents a moderate position balancing fiscal caution with the urgent needs of affected businesses.",
    },
  },
  {
    id: "pendlers",
    title: "Cross-border Cooperation",
    shortTitle: "Pendlers",
    description: "Policy evaluation for international collaboration",
    fullDescription: "During the COVID-19 pandemic, cross-border workers (pendlers) faced significant challenges due to border closures between countries. A panel of 22 government officials evaluated whether cross-border travel should be permitted for regular commuters.",
    question: "I agree that cross-border travel should be allowed for those who regularly travel from one country to another to work.",
    icon: Globe,
    experts: 22,
    dataType: "likert",
    scaleMin: 0,
    scaleMax: 100,
    scaleUnit: "agreement %",
    context: "Cross-border workers are essential for many regional economies, particularly in border areas between the Czech Republic, Germany, Austria, Poland, and Slovakia. Border closures during the pandemic disrupted the livelihoods of thousands of workers and created labor shortages in key sectors.",
    methodology: "Experts expressed their opinions using a 5-point Likert scale: Strongly disagree (0), Rather disagree (25), Neutral (50), Rather agree (75), Strongly agree (100). The BeCoMe method converted these to fuzzy numbers and calculated the optimal group decision.",
    opinions: [
      { role: "Chairman", value: 75 },
      { role: "Deputy Chairman", value: 25 },
      { role: "Deputy Minister of Interior", value: 0 },
      { role: "Deputy Minister of Defence", value: 0 },
      { role: "Deputy Minister of Foreign Affairs", value: 100 },
      { role: "Deputy Minister of Finance", value: 50 },
      { role: "Deputy Minister of Health", value: 25 },
      { role: "Deputy Minister of Industry and Trade", value: 75 },
      { role: "Deputy Minister of Transport", value: 25 },
      { role: "Deputy Minister of Education", value: 25 },
      { role: "Deputy Minister of Agriculture", value: 0 },
      { role: "Deputy Minister of Labour", value: 75 },
      { role: "Deputy Minister of Culture", value: 50 },
      { role: "Deputy Minister of Justice", value: 75 },
      { role: "Chairman of SSHR", value: 25 },
      { role: "Police President", value: 50 },
      { role: "Chief Hygienist", value: 0 },
      { role: "Border Police Chief", value: 25 },
      { role: "Regional Governor (Border)", value: 75 },
      { role: "Labour Union Rep", value: 100 },
      { role: "Employers Association Rep", value: 100 },
      { role: "Public Health Expert", value: 25 },
    ] as LikertOpinion[],
    result: {
      bestCompromise: 43.2,
      maxError: 12.5,
      interpretation: "The best compromise of 43.2% corresponds to 'Rather Disagree' on the Likert scale. The decision indicates that cross-border travel should NOT be generally allowed, though the high error margin (12.5%) reflects significant polarization among experts.",
    },
    note: "This case study uses illustrative fictional data for demonstration purposes and is not the result of actual research.",
  },
  {
    id: "floods",
    title: "Flood Prevention Planning",
    shortTitle: "Floods",
    description: "Risk assessment for flood prevention infrastructure",
    fullDescription: "Flood prevention in agricultural areas requires balancing multiple interests: environmental protection, agricultural productivity, economic considerations, and public safety. A panel of 13 diverse experts assessed what percentage of arable land in flood-prone areas should be converted to natural retention areas.",
    question: "What percentage reduction of arable land in flood areas is recommended to prevent floods?",
    icon: Droplets,
    experts: 13,
    dataType: "interval",
    scaleMin: 0,
    scaleMax: 100,
    scaleUnit: "%",
    context: "The Czech Republic experiences periodic flooding that causes significant damage to property and agriculture. Converting arable land to polders (water retention areas) can reduce flood risk but affects farmers' livelihoods and food production capacity. Finding the right balance is crucial.",
    methodology: "Each expert provided their opinion as a fuzzy triangular number representing the recommended percentage of land conversion. The diverse panel included hydrologists, municipal representatives, land owners, and other stakeholders to ensure comprehensive perspective.",
    opinions: [
      { role: "Hydrologist 1", bestProposal: 42, lowerLimit: 37, upperLimit: 47 },
      { role: "Hydrologist 2", bestProposal: 50, lowerLimit: 42, upperLimit: 50 },
      { role: "Nature Protection Officer", bestProposal: 7, lowerLimit: 5, upperLimit: 9 },
      { role: "Risk Management Expert", bestProposal: 40, lowerLimit: 37, upperLimit: 48 },
      { role: "Land Use Planner", bestProposal: 8, lowerLimit: 6, upperLimit: 11 },
      { role: "Civil Service Rep", bestProposal: 8, lowerLimit: 5, upperLimit: 9 },
      { role: "Municipality 1", bestProposal: 38, lowerLimit: 33, upperLimit: 43 },
      { role: "Municipality 2", bestProposal: 8, lowerLimit: 5, upperLimit: 8 },
      { role: "Economist", bestProposal: 14, lowerLimit: 10, upperLimit: 20 },
      { role: "Rescue Coordinator", bestProposal: 45, lowerLimit: 40, upperLimit: 50 },
      { role: "Land Owner 1", bestProposal: 3, lowerLimit: 2, upperLimit: 4 },
      { role: "Land Owner 2", bestProposal: 0, lowerLimit: 0, upperLimit: 2 },
      { role: "Land Owner 3", bestProposal: 2, lowerLimit: 0, upperLimit: 3 },
    ] as ExpertOpinion[],
    result: {
      bestCompromise: 20.4,
      maxError: 6.8,
      interpretation: "The best compromise recommends converting approximately 20.4% of arable land in flood areas to retention zones. This reflects a moderate approach that addresses flood risk while limiting impact on agricultural production. The relatively low error (6.8%) indicates reasonable consensus despite the diverse stakeholder interests.",
    },
  },
];

export function getCaseStudyById(id: string): CaseStudy | undefined {
  return caseStudies.find((cs) => cs.id === id);
}

export function getLikertLabel(value: number): string {
  if (value <= 12.5) return "Strongly Disagree";
  if (value <= 37.5) return "Rather Disagree";
  if (value <= 62.5) return "Neutral";
  if (value <= 87.5) return "Rather Agree";
  return "Strongly Agree";
}
