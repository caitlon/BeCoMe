import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Send, Sparkles, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useMediaQuery } from "@/hooks/use-media-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { cn } from "@/lib/utils";
import type { ProjectWithRole } from "@/types/api";
import { MAX_QUESTION_LENGTH } from "./AssistantComposer";

const SUGGESTION_INDEXES = [0, 1, 2] as const;

function ProjectScopeLabel({ projectId }: { readonly projectId: string }) {
  const { t } = useTranslation("assistant");
  // Reads the project page's cached entry (same key) and never fetches on its
  // own, so opening the panel adds no request; without the entry the label is
  // generic. The real queryFn matters: the options of the last observer are
  // what a refetch of the shared key runs, so a placeholder here would break
  // the project page's own invalidation while the panel is open.
  const projectQuery = useQuery<ProjectWithRole>({
    queryKey: queryKeys.project(projectId),
    queryFn: () => api.getProject(projectId),
    enabled: false,
  });

  return projectQuery.data?.name
    ? t("panel.scopeProject", { name: projectQuery.data.name })
    : t("panel.scopeGeneral");
}

export interface AssistantPanelProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly projectId: string | null;
  readonly onSuggestion?: (text: string) => void;
}

/**
 * The panel shell: header, empty state, a composer that is not wired yet and
 * the footer. A right-hand sheet that leaves the page interactive on desktop,
 * a modal bottom sheet below the md breakpoint.
 */
export function AssistantPanel({ open, onOpenChange, projectId, onSuggestion }: AssistantPanelProps) {
  const { t } = useTranslation("assistant");
  const { t: tCommon } = useTranslation("common");
  const isDesktop = useMediaQuery("(min-width: 768px)");

  const scoped = Boolean(projectId);
  const suggestionsKey = scoped ? "empty.suggestionsProject" : "empty.suggestionsGeneral";

  return (
    <Sheet open={open} onOpenChange={onOpenChange} modal={!isDesktop}>
      <SheetContent
        side={isDesktop ? "right" : "bottom"}
        showCloseButton={false}
        onInteractOutside={(event) => event.preventDefault()}
        className={cn(
          "flex flex-col gap-0 p-0",
          isDesktop ? "w-full sm:max-w-[440px]" : "h-[94dvh] rounded-t-2xl",
        )}
      >
        <header className="flex items-center gap-2.5 border-b px-4 pb-2.5 pt-3.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <SheetTitle className="font-display text-lg font-medium leading-tight">
              {t("panel.title")}
            </SheetTitle>
            <SheetDescription className="truncate text-xs">
              {projectId ? <ProjectScopeLabel projectId={projectId} /> : t("panel.scopeGeneral")}
            </SheetDescription>
          </div>
          <Button variant="ghost" size="icon" disabled aria-label={t("panel.clear")} title={t("panel.clear")}>
            <Trash2 className="h-4 w-4" />
          </Button>
          <SheetClose asChild>
            <Button variant="ghost" size="icon" aria-label={tCommon("a11y.close")} title={tCommon("a11y.close")}>
              <X className="h-4 w-4" />
            </Button>
          </SheetClose>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-7 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-muted">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <h3 className="mb-1.5 font-display text-lg font-medium">
            {scoped ? t("empty.titleProject") : t("empty.titleGeneral")}
          </h3>
          <p className="mb-4 text-sm text-muted-foreground">
            {t("empty.hint")}
            <br />
            <span className="text-xs">{t("panel.seesOnly")}</span>
          </p>
          <div className="flex flex-col gap-1.5">
            {SUGGESTION_INDEXES.map((index) => {
              const text = t(`${suggestionsKey}.${index}`);
              return (
                <Button
                  key={index}
                  variant="outline"
                  className="h-auto justify-start whitespace-normal bg-card px-3 py-2 text-left font-normal"
                  onClick={() => onSuggestion?.(text)}
                >
                  {text}
                </Button>
              );
            })}
          </div>
        </div>

        <div className="border-t px-4 pb-3 pt-2.5">
          <div className="flex items-end gap-2">
            <Textarea
              disabled
              rows={1}
              placeholder={t("composer.placeholder")}
              aria-label={t("composer.placeholder")}
              className="min-h-11 resize-none"
            />
            <Button size="icon" disabled aria-label={tCommon("send")} title={tCommon("send")}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
            <span>{t("composer.hint")}</span>
            <span className="font-mono">0 / {MAX_QUESTION_LENGTH}</span>
          </div>
        </div>

        <p className="px-4 pb-2.5 text-center text-[11px] text-muted-foreground">{t("panel.footer")}</p>
      </SheetContent>
    </Sheet>
  );
}
