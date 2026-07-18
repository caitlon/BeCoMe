import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, ChevronDown, Download, FileText, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { ProjectWithRole, Opinion, CalculationResult } from "@/types/api";
import { useToast } from "@/hooks/use-toast";
import { CentroidBarChart } from "@/components/visualizations/CentroidBarChart";
import { cn } from "@/lib/utils";
import { TriangleVisualization } from "./TriangleVisualization";

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
  const { t, i18n } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();
  const { toast } = useToast();
  const [exporting, setExporting] = useState<"pdf" | "csv" | null>(null);
  const showIndividualId = useId();

  const handleExport = async (format: "pdf" | "csv") => {
    setExporting(format);
    try {
      const lang = i18n.language.startsWith("cs") ? "cs" : "en";
      const blob = await api.exportProjectResult(project.id, format, lang);
      const slug =
        project.name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "") || "project";
      downloadBlob(blob, `${slug}-results.${format}`);
      toast({ title: t("resultExport.success") });
    } catch (error) {
      toast({
        title: t("toast.error"),
        description:
          error instanceof Error ? error.message : t("resultExport.error"),
        variant: "destructive",
      });
    } finally {
      setExporting(null);
    }
  };

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
      <div className="flex justify-end">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={exporting !== null}>
              {exporting === null ? (
                <Download className="mr-2 h-4 w-4" />
              ) : (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {exporting === null
                ? t("resultExport.button")
                : t("resultExport.exporting")}
              <ChevronDown className="ml-2 h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => void handleExport("pdf")}>
              <FileText className="mr-2 h-4 w-4" />
              {t("resultExport.pdf")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void handleExport("csv")}>
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              {t("resultExport.csv")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Best Compromise */}
      <Card className="border-2 border-primary">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {t("detail.bestCompromise")}
            <span className="text-sm font-normal text-muted-foreground">
              (ΓΩMean)
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center mb-4">
            <div>
              <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.lower")}</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.lower.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.peak")}</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.peak.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.upper")}</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.upper.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="text-center border-t pt-4">
            <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.centroid")}</div>
            <div className="font-mono text-3xl font-medium">
              {result.best_compromise.centroid.toFixed(2)}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Arithmetic Mean & Median */}
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

      {/* Max Error & Experts */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm">{t("detail.maxError")}</span>
            <div className="flex items-center gap-2">
              <Badge className={cn("text-xs", agreementClasses.badge)}>
                {t(`detail.agreement.${agreementLevel}`)}
              </Badge>
              <span className="font-mono font-medium">
                {result.max_error.toFixed(2)}
              </span>
            </div>
          </div>
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
          <Tabs defaultValue="triangle" className="space-y-4">
            <TabsList className="w-full">
              <TabsTrigger value="triangle" className="flex-1">
                {t("detail.vizTab.triangle")}
              </TabsTrigger>
              <TabsTrigger value="centroid" className="flex-1">
                {t("detail.vizTab.centroid")}
              </TabsTrigger>
            </TabsList>

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
