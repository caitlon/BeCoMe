import { useState, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

type CreateProjectFormData = {
  name: string;
  description?: string;
  scale_min: number;
  scale_max: number;
  scale_unit: string;
};

interface CreateProjectModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function CreateProjectModal({ open, onOpenChange, onSuccess }: CreateProjectModalProps) {
  const { t } = useTranslation("projects");
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const createProjectSchema = useMemo(
    () =>
      z.object({
        name: z.string().min(1, t("create.validation.nameRequired")).max(255),
        description: z.string().max(1000).optional(),
        scale_min: z.coerce.number(),
        scale_max: z.coerce.number(),
        scale_unit: z.string().min(1, t("create.validation.unitRequired")).max(50),
      }).refine(data => data.scale_max > data.scale_min, {
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
        description: error instanceof Error ? error.message : t("toast.createFailed"),
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
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">{t("create.name")} *</Label>
            <Input
              id="name"
              placeholder={t("create.namePlaceholder")}
              {...register("name")}
              className={errors.name ? "border-destructive" : ""}
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">{t("create.description")}</Label>
            <Textarea
              id="description"
              placeholder={t("create.descriptionPlaceholder")}
              rows={3}
              {...register("description")}
            />
          </div>

          <div className="space-y-2">
            <Label>{t("create.scaleSettings")}</Label>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Input
                  type="number"
                  placeholder="Min"
                  {...register("scale_min")}
                  className={errors.scale_min ? "border-destructive" : ""}
                />
                <span className="text-xs text-muted-foreground mt-1 block">{t("create.scaleMin")}</span>
              </div>
              <div>
                <Input
                  type="number"
                  placeholder="Max"
                  {...register("scale_max")}
                  className={errors.scale_max ? "border-destructive" : ""}
                />
                <span className="text-xs text-muted-foreground mt-1 block">{t("create.scaleMax")}</span>
              </div>
              <div>
                <Input
                  placeholder={t("create.scaleUnitPlaceholder")}
                  {...register("scale_unit")}
                  className={errors.scale_unit ? "border-destructive" : ""}
                />
                <span className="text-xs text-muted-foreground mt-1 block">{t("create.scaleUnit")}</span>
              </div>
            </div>
            {errors.scale_max && (
              <p className="text-sm text-destructive">{errors.scale_max.message}</p>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("create.cancel")}
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("create.creating")}
                </>
              ) : (
                t("create.create")
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
