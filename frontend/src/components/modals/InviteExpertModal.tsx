import { useState, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";
import { Check, Info } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { FormField, SubmitButton } from "@/components/forms";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

type InviteFormData = {
  email: string;
};

interface InviteExpertModalProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly projectId?: string;
  readonly projectName?: string;
}

export function InviteExpertModal({
  open,
  onOpenChange,
  projectId,
  projectName,
}: InviteExpertModalProps) {
  const { t } = useTranslation("projects");
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const inviteSchema = useMemo(
    () =>
      z.object({
        email: z.string().email(t("invite.validation.emailInvalid")),
      }),
    [t]
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<InviteFormData>({
    resolver: zodResolver(inviteSchema),
    mode: "onTouched",
  });

  const handleClose = () => {
    onOpenChange(false);
    setTimeout(() => {
      setIsSuccess(false);
      reset();
    }, 200);
  };

  const onSubmit = async (data: InviteFormData) => {
    if (!projectId) return;

    setIsLoading(true);
    try {
      await api.inviteExpert(projectId, data.email);
      setIsSuccess(true);
    } catch (error) {
      toast({
        title: t("invite.errorTitle"),
        description:
          error instanceof Error ? error.message : t("invite.errorMessage"),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleInviteAnother = () => {
    setIsSuccess(false);
    reset();
  };

  if (isSuccess) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader className="text-center">
            <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
              <Check className="h-6 w-6 text-success" />
            </div>
            <DialogTitle className="font-display text-xl font-normal">
              {t("invite.title")}
            </DialogTitle>
            <DialogDescription className="text-lg font-medium">
              {t("invite.successTitle")}
            </DialogDescription>
          </DialogHeader>

          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={handleInviteAnother}>
              {t("invite.inviteAnother")}
            </Button>
            <Button onClick={handleClose}>{t("invite.done")}</Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display text-xl font-normal">
            {t("invite.title")}
          </DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            {t("invite.inviteTo")}{" "}
            <span className="font-medium text-foreground">{projectName}</span>
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            label={`${t("invite.email")} *`}
            type="email"
            placeholder={t("invite.emailPlaceholder")}
            error={errors.email}
            {...register("email")}
          />

          <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted p-3 rounded-lg">
            <Info className="h-4 w-4 shrink-0 mt-0.5" />
            <p>{t("invite.info")}</p>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={handleClose}>
              {t("invite.cancel")}
            </Button>
            <SubmitButton isLoading={isLoading} loadingText={t("invite.inviting")}>
              {t("invite.invite")}
            </SubmitButton>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
