import { caseStudies } from "@/data/caseStudies";

/**
 * The paths a visitor can open without signing in and that are worth serving
 * as prerendered HTML. The routes behind a login and the catch-all are left
 * out on purpose.
 */
export const publicRoutes: readonly string[] = [
  "/",
  "/about",
  "/docs",
  "/faq",
  "/privacy",
  "/terms",
  "/case-studies",
  ...caseStudies.map((caseStudy) => `/case-study/${caseStudy.id}`),
];
