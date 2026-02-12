import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { LocalizedCaseStudy } from "@/hooks/useLocalizedCaseStudies";

interface CaseStudyCardProps {
  study: LocalizedCaseStudy;
  showScale?: boolean;
}

export function CaseStudyCard({ study, showScale = false }: CaseStudyCardProps) {
  const { t } = useTranslation("caseStudies");
  const IconComponent = study.icon;

  return (
    <Link to={`/case-study/${study.id}`}>
      <Card className="h-full group hover:shadow-lg hover:border-primary/30 transition-all duration-300 cursor-pointer">
        <CardContent className="pt-6 pb-6">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
              <IconComponent className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" aria-hidden="true" />
            </div>
            <div>
              <h3 className="font-display font-medium text-lg mb-1 group-hover:text-primary transition-colors">
                {study.title}
              </h3>
              <p className="text-sm text-muted-foreground mb-3">
                {study.description}
              </p>
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3" aria-hidden="true" />
                  <span className="font-mono">
                    {study.experts} {t("common.experts")}
                  </span>
                </span>
                {showScale && (
                  <span className="font-mono bg-muted px-2 py-0.5 rounded">
                    {study.scaleMin}–{study.scaleMax} {study.scaleUnit}
                  </span>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
