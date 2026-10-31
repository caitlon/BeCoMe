import { useCallback, useEffect, useId, useState } from "react";
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
import { PasswordInput, SubmitButton } from "@/components/forms";
import { api } from "@/lib/api";
import { describeError } from "@/lib/errorMessages";
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
 * deleted, or transferred to another member (GDPR Art. 17 right to erasure), and the
 * current password confirms the request, as it does for a password change. Every opening
 * starts from the default choices and an empty password. Enter in the password field
 * submits the form.
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
  const [password, setPassword] = useState("");
  const passwordHintId = useId();
  const [submitting, setSubmitting] = useState(false);
  const [failedMessage, setFailedMessage] = useState<string | null>(null);

  const loadOwnedProjects = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    setFailedMessage(null);
    // Choices and the password belong to one opening: a choice made earlier can name a member
    // who has since left, and a password typed earlier should not wait in a closed dialog.
    setChoices({});
    setPassword("");
    try {
      const projects = await api.getProjects();
      const owned = projects.filter((p) => p.role === "admin");
      const entries = await Promise.all(
        owned.map(async (p) => {
          // The example project cannot take invitations, so every member besides its admin is
          // a demo account, which the API never accepts as a new admin: offer only deletion.
          if (p.is_example) return [p.id, []] as const;
          return [
            p.id,
            (await api.getMembers(p.id)).filter((m) => m.user_id !== currentUserId),
          ] as const;
        })
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
    setFailedMessage(null);
    try {
      await api.deleteAccount(password, buildDispositions());
      await onConfirmed();
    } catch (err) {
      logger.error("Account deletion failed", { error: String(err) });
      setFailedMessage(describeError(err, tCommon, t("deleteAccount.failed")));
      setSubmitting(false);
    }
  };

  const handleSubmit = (event: React.SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (loading || loadError || submitting || password === "") return;
    handleConfirm();
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

        <form onSubmit={handleSubmit} className="grid gap-4">
          <div className="py-2">
            {loading ? (
              <output
                className="flex justify-center py-6"
                aria-label={tCommon("a11y.loading")}
              >
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </output>
            ) : (
              <>
                {ownedProjects.length > 0 && (
                  <div className="space-y-3 mb-4">
                    {ownedProjects.map((p) => (
                      <div
                        key={p.id}
                        className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                      >
                        <span className="text-sm font-medium truncate">{p.name}</span>
                        <Select
                          value={choiceFor(p.id)}
                          onValueChange={(v) => setChoices((c) => ({ ...c, [p.id]: v }))}
                        >
                          <SelectTrigger className="w-full sm:w-56 sm:shrink-0">
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
                {!loadError && (
                  <div className="mb-4 space-y-2">
                    <p id={passwordHintId} className="text-sm text-muted-foreground">
                      {t("deleteAccount.passwordHint")}
                    </p>
                    <PasswordInput
                      label={t("deleteAccount.password")}
                      autoComplete="current-password"
                      aria-describedby={passwordHintId}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      readOnly={submitting}
                    />
                  </div>
                )}
                <p className="text-sm font-medium text-destructive">
                  {t("deleteModal.details.noUndo")}
                </p>
                {(loadError || failedMessage) && (
                  <p className="text-sm text-destructive mt-2" role="alert">
                    {loadError ? t("deleteAccount.loadFailed") : failedMessage}
                  </p>
                )}
              </>
            )}
          </div>

          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              {tCommon("cancel")}
            </Button>
            <SubmitButton
              type="submit"
              variant="destructive"
              isLoading={submitting}
              disabled={loading || loadError || password === ""}
              loadingText={t("deleteModal.deleting")}
            >
              {t("deleteModal.confirm")}
            </SubmitButton>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
