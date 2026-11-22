import { caseStudies } from "@/data/caseStudies";

/**
 * What the head of a public page says about it. The keys point into the locale
 * files, so the text is the page's own and a rewrite there reaches the head.
 */
export interface PublicRouteMeta {
  readonly path: string;
  /** Key of the page title in the common namespace. */
  readonly titleKey: string;
  /** Key, in the page's own namespace, of the text that fills `{{name}}` in the title. */
  readonly titleNameKey?: string;
  /** False when the page title stands alone, without the " - BeCoMe" suffix. */
  readonly titleSuffix: boolean;
  /** The description, as "namespace:key". */
  readonly descriptionKey: string;
}

/**
 * The paths a visitor can open without signing in and that are worth serving
 * as prerendered HTML, with the keys of their title and description. The routes
 * behind a login and the catch-all are left out on purpose.
 */
export const publicRouteMeta: readonly PublicRouteMeta[] = [
  { path: "/", titleKey: "pageTitle.landing", titleSuffix: false, descriptionKey: "landing:hero.subtitle" },
  { path: "/about", titleKey: "pageTitle.about", titleSuffix: true, descriptionKey: "about:hero.subtitle" },
  { path: "/docs", titleKey: "pageTitle.documentation", titleSuffix: true, descriptionKey: "docs:subtitle" },
  { path: "/faq", titleKey: "pageTitle.faq", titleSuffix: true, descriptionKey: "faq:subtitle" },
  { path: "/privacy", titleKey: "pageTitle.privacy", titleSuffix: true, descriptionKey: "privacy:meta.subtitle" },
  { path: "/terms", titleKey: "pageTitle.terms", titleSuffix: true, descriptionKey: "terms:meta.subtitle" },
  {
    path: "/case-studies",
    titleKey: "pageTitle.caseStudies",
    titleSuffix: true,
    descriptionKey: "caseStudies:listing.subtitle",
  },
  ...caseStudies.map((caseStudy) => ({
    path: `/case-study/${caseStudy.id}`,
    titleKey: "pageTitle.caseStudyDetail",
    titleNameKey: `caseStudies:${caseStudy.id}.title`,
    titleSuffix: true,
    descriptionKey: `caseStudies:${caseStudy.id}.description`,
  })),
];

export const publicRoutes: readonly string[] = publicRouteMeta.map((route) => route.path);
