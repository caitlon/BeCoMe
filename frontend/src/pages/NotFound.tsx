import { Link, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { Navbar } from "@/components/layout/Navbar";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const NotFound = () => {
  const { t } = useTranslation();
  const location = useLocation();
  useDocumentTitle(t("pageTitle.notFound"));

  useEffect(() => {
    console.error(
      "404 Error: User attempted to access non-existent route:",
      location.pathname
    );
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main id="main-content" className="flex min-h-[calc(100vh-4rem)] items-center justify-center">
        <div className="text-center">
          <h1 className="mb-4 text-4xl font-bold">404</h1>
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
};

export default NotFound;
