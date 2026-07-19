import { useId } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ProjectWithRole, Opinion, CalculationResult } from "@/types/api";
import { CentroidBarChart } from "@/components/visualizations/CentroidBarChart";
import { cn } from "@/lib/utils";
import { TriangleVisualization } from "./TriangleVisualization";
import { OpinionLandscape } from "./OpinionLandscape";

export interface ResultsSectionProps {
  result: CalculationResult | null;
  project: ProjectWithRole;
  showIndividual: boolean;
  setShowIndividual: (v: boolean) => void;
  opinions: Opinion[];
}

export const ResultsSection = ({
  result,
  project,
  showIndividual,
  setShowIndividual,
  opinions,
}: ResultsSectionProps) => {
  const { t } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();
  const showIndividualId = useId();

  if (!result || opinions.length === 0) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <p className="text-muted-foreground">
            {t("detail.noResults")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const scaleRange = project.scale_max - project.scale_min;
  const errorPercent = (result.max_error / scaleRange) * 100;

  let agreementLevel: "high" | "moderate" | "low";
  if (errorPercent <= 20) {
    agreementLevel = "high";
  } else if (errorPercent <= 40) {
    agreementLevel = "moderate";
  } else {
    agreementLevel = "low";
  }
  const agreementClasses = {
    high: {
      badge: "bg-success text-success-foreground hover:bg-success/90",
      progress: "[&>div]:bg-success",
    },
    moderate: {
      badge: "bg-warning text-warning-foreground hover:bg-warning/90",
      progress: "[&>div]:bg-warning",
    },
    low: {
      badge: "bg-error text-error-foreground hover:bg-error/90",
      progress: "[&>div]:bg-error",
    },
  }[agreementLevel];

  return (
    <div className="space-y-6">
      {/* Best Compromise */}
      <Card className="border-2 border-primary">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {t("detail.bestCompromise")}
            <Badge className="text-xs">{t("detail.resultBadge")}</Badge>
            <span className="text-sm font-normal text-muted-foreground ml-auto">
              (ΓΩMean)
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center mb-4">
            <div className="text-xs text-muted-foreground uppercase">{t("detail.resultValue")}</div>
            <div className="flex items-baseline justify-center gap-2 flex-wrap">
              <span className="font-mono text-4xl font-bold text-primary">
                {result.best_compromise.centroid.toFixed(2)}
              </span>
              <span className="font-mono text-sm text-muted-foreground">
                ± {result.max_error.toFixed(2)}
              </span>
            </div>
            <div className="mt-2">
              <Badge className={cn("text-xs font-normal", agreementClasses.badge)}>
                {t(`detail.confidenceLevel.${agreementLevel}`)} {t("detail.confidence")}
              </Badge>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center border-t pt-4">
            <div>
              <div className="text-xs text-muted-foreground">{tFuzzy("fuzzy.lowerDesc")}</div>
              <div className="font-mono text-sm text-secondary-foreground">
                {result.best_compromise.lower.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{tFuzzy("fuzzy.peakDesc")}</div>
              <div className="font-mono text-sm text-secondary-foreground">
                {result.best_compromise.peak.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{tFuzzy("fuzzy.upperDesc")}</div>
              <div className="font-mono text-sm text-secondary-foreground">
                {result.best_compromise.upper.toFixed(2)}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Arithmetic Mean & Median */}
      <Collapsible>
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full justify-between px-2 text-muted-foreground [&[data-state=open]>svg]:rotate-180"
          >
            <span className="text-sm font-medium">{t("detail.supportingCalcs")}</span>
            <ChevronDown className="h-4 w-4 transition-transform" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{t("detail.arithmeticMean")}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="font-mono text-sm whitespace-nowrap tabular-nums overflow-x-auto">
                  {result.arithmetic_mean.lower.toFixed(2)} | {result.arithmetic_mean.peak.toFixed(2)} |{" "}
                  {result.arithmetic_mean.upper.toFixed(2)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {tFuzzy("fuzzy.centroid")}: {result.arithmetic_mean.centroid.toFixed(2)}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{t("detail.median")}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="font-mono text-sm whitespace-nowrap tabular-nums overflow-x-auto">
                  {result.median.lower.toFixed(2)} | {result.median.peak.toFixed(2)} |{" "}
                  {result.median.upper.toFixed(2)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {tFuzzy("fuzzy.centroid")}: {result.median.centroid.toFixed(2)}
                </div>
              </CardContent>
            </Card>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Confidence & Experts */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex justify-between items-center mb-1">
            <span className="text-sm">
              {t("detail.confidence")}{" "}
              <span className="text-xs text-muted-foreground font-normal">(Δmax)</span>
            </span>
            <div className="flex items-center gap-2">
              <Badge className={cn("text-xs", agreementClasses.badge)}>
                {t(`detail.agreement.${agreementLevel}`)}
              </Badge>
              <span className="font-mono font-medium">
                {result.max_error.toFixed(2)}
              </span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mb-2">{t("detail.confidenceHint")}</p>
          <Progress value={Math.min(errorPercent, 100)} className={cn("h-2", agreementClasses.progress)} />
          <div className="flex justify-between items-center mt-4 text-sm text-muted-foreground">
            <span>{t("detail.experts")}</span>
            <span className="font-mono">{result.num_experts}</span>
          </div>
        </CardContent>
      </Card>

      {/* Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("detail.visualization")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="landscape" className="space-y-4">
            <TabsList className="w-full">
              <TabsTrigger value="landscape" className="flex-1">
                {t("detail.vizTab.landscape")}
              </TabsTrigger>
              <TabsTrigger value="triangle" className="flex-1">
                {t("detail.vizTab.triangle")}
              </TabsTrigger>
              <TabsTrigger value="centroid" className="flex-1">
                {t("detail.vizTab.centroid")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="landscape">
              <OpinionLandscape result={result} project={project} opinions={opinions} />
            </TabsContent>

            <TabsContent value="triangle">
              <TriangleVisualization
                result={result}
                project={project}
                showIndividual={showIndividual}
                opinions={opinions}
              />
              <div className="flex items-center justify-between mt-4">
                <div className="flex gap-4 text-xs">
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-chart-mean" />
                    <span>{tFuzzy("fuzzy.mean")}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-chart-median" />
                    <span>{tFuzzy("fuzzy.median")}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-foreground" />
                    <span>{tFuzzy("fuzzy.best")}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id={showIndividualId}
                    checked={showIndividual}
                    onCheckedChange={(checked) => setShowIndividual(!!checked)}
                  />
                  <Label htmlFor={showIndividualId} className="text-xs cursor-pointer">
                    {t("detail.showIndividual")}
                  </Label>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="centroid">
              <CentroidBarChart opinions={opinions} result={result} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};
