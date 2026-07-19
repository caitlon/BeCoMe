import { useLocation } from "react-router-dom";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { NotFoundState } from "@/components/NotFoundState";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { logger } from "@/lib/logger";

const NotFound = () => {
  const { t } = useTranslation();
  const location = useLocation();
  useDocumentTitle(t("pageTitle.notFound"));

  useEffect(() => {
    logger.warn("404 Error: route not found", { path: location.pathname });
  }, [location.pathname]);

  return <NotFoundState />;
};

export default NotFound;
