import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, ChevronDown, Download, FileText, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { ProjectWithRole } from "@/types/api";
import { useToast } from "@/hooks/use-toast";
import { toSupportedLanguage } from "@/i18n";

export interface ResultExportMenuProps {
  project: ProjectWithRole;
}

/** Result export (PDF / CSV) dropdown, rendered in the project header. */
export const ResultExportMenu = ({ project }: ResultExportMenuProps) => {
  const { t, i18n } = useTranslation("projects");
  const { toast } = useToast();
  const [exporting, setExporting] = useState<"pdf" | "csv" | null>(null);

  const handleExport = async (format: "pdf" | "csv") => {
    setExporting(format);
    try {
      const lang = toSupportedLanguage(i18n.language);
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
        description: error instanceof Error ? error.message : t("resultExport.error"),
        variant: "destructive",
      });
    } finally {
      setExporting(null);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={exporting !== null}>
          {exporting === null ? (
            <Download className="mr-2 h-4 w-4" />
          ) : (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          )}
          {exporting === null ? t("resultExport.button") : t("resultExport.exporting")}
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
  );
};
