import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Navbar } from "@/components/layout/Navbar";

/**
 * Shared not-found screen, used both for unmatched routes (`NotFound`) and
 * for a resolved route whose resource does not exist (e.g. an unknown
 * case-study id in `CaseStudy`).
 */
export function NotFoundState() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main id="main-content" className="flex min-h-[calc(100vh-4rem)] items-center justify-center">
        <div className="text-center">
          <h1 className="font-display text-4xl font-normal tracking-tight mb-4">{t("notFound.code")}</h1>
          <p className="mb-4 text-xl text-muted-foreground">
            {t("notFound.description")}
          </p>
          <Link to="/" className="text-primary underline hover:text-primary/80">
            {t("notFound.backHome")}
          </Link>
        </div>
      </main>
    </div>
  );
}
