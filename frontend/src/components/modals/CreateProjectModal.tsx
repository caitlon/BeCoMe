import { useState, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FormField, FormTextarea, SubmitButton } from "@/components/forms";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

type CreateProjectFormData = {
  name: string;
  description?: string;
  scale_min: number;
  scale_max: number;
  scale_unit: string;
};

interface CreateProjectModalProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onSuccess: () => void;
}

export function CreateProjectModal({
  open,
  onOpenChange,
  onSuccess,
}: CreateProjectModalProps) {
  const { t } = useTranslation("projects");
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const createProjectSchema = useMemo(
    () =>
      z
        .object({
          name: z.string().min(1, t("create.validation.nameRequired")).max(255),
          description: z.string().max(1000).optional(),
          scale_min: z.coerce.number(),
          scale_max: z.coerce.number(),
          scale_unit: z
            .string()
            .min(1, t("create.validation.unitRequired"))
            .max(50),
        })
        .refine((data) => data.scale_max > data.scale_min, {
          message: t("create.validation.maxGreaterMin"),
          path: ["scale_max"],
        }),
    [t]
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: {
      scale_min: 0,
      scale_max: 100,
      scale_unit: "",
    },
  });

  const onSubmit = async (data: CreateProjectFormData) => {
    setIsLoading(true);
    try {
      await api.createProject({
        name: data.name,
        description: data.description,
        scale_min: data.scale_min,
        scale_max: data.scale_max,
        scale_unit: data.scale_unit,
      });
      toast({ title: t("create.successTitle") });
      reset();
      onOpenChange(false);
      onSuccess();
    } catch (error) {
      toast({
        title: t("create.errorTitle"),
        description:
          /* v8 ignore next */
          error instanceof Error ? error.message : t("toast.createFailed"),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display text-xl font-normal">
            {t("create.title")}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("create.dialogDescription")}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            label={`${t("create.name")} *`}
            placeholder={t("create.namePlaceholder")}
            error={errors.name}
            {...register("name")}
          />

          <FormTextarea
            label={t("create.description")}
            placeholder={t("create.descriptionPlaceholder")}
            rows={3}
            {...register("description")}
          />

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium leading-none">{t("create.scaleSettings")}</legend>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label htmlFor="scale-min" className="sr-only">{t("create.scaleMin")}</Label>
                <Input
                  id="scale-min"
                  type="number"
                  placeholder={t("create.scaleMinPlaceholder")}
                  {...register("scale_min")}
                  className={cn(/* v8 ignore next */ errors.scale_min && "border-destructive")}
                />
                <span className="text-xs text-muted-foreground mt-1 block" aria-hidden="true">
                  {t("create.scaleMin")}
                </span>
              </div>
              <div>
                <Label htmlFor="scale-max" className="sr-only">{t("create.scaleMax")}</Label>
                <Input
                  id="scale-max"
                  type="number"
                  placeholder={t("create.scaleMaxPlaceholder")}
                  {...register("scale_max")}
                  className={cn(errors.scale_max && "border-destructive")}
                />
                <span className="text-xs text-muted-foreground mt-1 block" aria-hidden="true">
                  {t("create.scaleMax")}
                </span>
              </div>
              <div>
                <Label htmlFor="scale-unit" className="sr-only">{t("create.scaleUnit")}</Label>
                <Input
                  id="scale-unit"
                  placeholder={t("create.scaleUnitPlaceholder")}
                  {...register("scale_unit")}
                  className={cn(errors.scale_unit && "border-destructive")}
                />
                <span className="text-xs text-muted-foreground mt-1 block" aria-hidden="true">
                  {t("create.scaleUnit")}
                </span>
              </div>
            </div>
            {errors.scale_max && (
              <p className="text-sm text-destructive">
                {errors.scale_max.message}
              </p>
            )}
          </fieldset>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t("create.cancel")}
            </Button>
            <SubmitButton isLoading={isLoading} loadingText={t("create.creating")}>
              {t("create.create")}
            </SubmitButton>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
