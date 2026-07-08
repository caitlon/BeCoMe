import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { SubmitButton } from "@/components/forms";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { Member, ProjectDisposition, ProjectWithRole } from "@/types/api";

const DELETE_VALUE = "delete";
const TRANSFER_PREFIX = "transfer:";

interface DeleteAccountDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly currentUserId: string;
  readonly onConfirmed: () => Promise<void>;
}

/**
 * Account-deletion dialog. Each project the user still owns must be handled first:
 * deleted, or transferred to another member (GDPR Art. 17 right to erasure).
 */
export function DeleteAccountDialog({
  open,
  onOpenChange,
  currentUserId,
  onConfirmed,
}: DeleteAccountDialogProps) {
  const { t } = useTranslation("profile");
  const { t: tCommon } = useTranslation("common");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [ownedProjects, setOwnedProjects] = useState<ProjectWithRole[]>([]);
  const [membersByProject, setMembersByProject] = useState<Record<string, Member[]>>({});
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [failed, setFailed] = useState(false);

  const loadOwnedProjects = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const projects = await api.getProjects();
      const owned = projects.filter((p) => p.role === "admin");
      const entries = await Promise.all(
        owned.map(
          async (p) =>
            [p.id, (await api.getMembers(p.id)).filter((m) => m.user_id !== currentUserId)] as const
        )
      );
      setOwnedProjects(owned);
      setMembersByProject(Object.fromEntries(entries));
    } catch (err) {
      logger.error("Failed to load owned projects for deletion", { error: String(err) });
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [currentUserId]);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load owned projects on open
    loadOwnedProjects();
  }, [open, loadOwnedProjects]);

  const choiceFor = (id: string) => choices[id] ?? DELETE_VALUE;

  const buildDispositions = (): ProjectDisposition[] =>
    ownedProjects.map((p) => {
      const choice = choiceFor(p.id);
      if (choice.startsWith(TRANSFER_PREFIX)) {
        return {
          project_id: p.id,
          action: "transfer",
          new_admin_id: choice.slice(TRANSFER_PREFIX.length),
        };
      }
      return { project_id: p.id, action: "delete" };
    });

  const handleConfirm = async () => {
    setSubmitting(true);
    setFailed(false);
    try {
      await api.deleteAccount(buildDispositions());
      await onConfirmed();
    } catch (err) {
      logger.error("Account deletion failed", { error: String(err) });
      setFailed(true);
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {t("deleteModal.title")}
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {ownedProjects.length > 0 ? t("deleteAccount.ownedIntro") : t("deleteModal.description")}
          </DialogDescription>
        </DialogHeader>

        <div className="py-2">
          {loading ? (
            <div
              className="flex justify-center py-6"
              role="status"
              aria-label={tCommon("aria.loading")}
            >
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {ownedProjects.length > 0 && (
                <div className="space-y-3 mb-4">
                  {ownedProjects.map((p) => (
                    <div key={p.id} className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium truncate">{p.name}</span>
                      <Select
                        value={choiceFor(p.id)}
                        onValueChange={(v) => setChoices((c) => ({ ...c, [p.id]: v }))}
                      >
                        <SelectTrigger className="w-56 shrink-0">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={DELETE_VALUE}>
                            {t("deleteAccount.deleteProject")}
                          </SelectItem>
                          {(membersByProject[p.id] ?? []).map((m) => (
                            <SelectItem key={m.user_id} value={`${TRANSFER_PREFIX}${m.user_id}`}>
                              {t("deleteAccount.transferTo", {
                                name: `${m.first_name} ${m.last_name ?? ""}`.trim(),
                              })}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-sm font-medium text-destructive">
                {t("deleteModal.details.noUndo")}
              </p>
              {(loadError || failed) && (
                <p className="text-sm text-destructive mt-2" role="alert">
                  {loadError ? t("deleteAccount.loadFailed") : t("deleteAccount.failed")}
                </p>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            {tCommon("cancel")}
          </Button>
          <SubmitButton
            type="button"
            variant="destructive"
            onClick={handleConfirm}
            isLoading={submitting}
            disabled={loading || loadError}
            loadingText={t("deleteModal.deleting")}
          >
            {t("deleteModal.confirm")}
          </SubmitButton>
        </div>
      </DialogContent>
    </Dialog>
  );
}
