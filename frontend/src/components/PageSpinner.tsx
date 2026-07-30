import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";

interface PageSpinnerProps {
  readonly className?: string;
}

/**
 * The one loading indicator for a whole page or route. Uses <output>, which
 * carries an implicit `status` role, so the label and the visually hidden text
 * both reach a screen reader.
 */
export function PageSpinner({ className }: PageSpinnerProps) {
  const { t } = useTranslation();

  return (
    <output aria-label={t("a11y.loading")} className={cn(className)}>
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <span className="sr-only">{t("common.loading")}</span>
    </output>
  );
}
