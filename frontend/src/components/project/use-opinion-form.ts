import { useEffect, useMemo } from "react";
import { useForm, UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { Opinion, ProjectWithRole } from "@/types/api";

type Translate = (key: string, options?: Record<string, unknown>) => string;

const numericField = (requiredMessage: string, invalidMessage: string) =>
  z
    .string()
    .trim()
    .min(1, requiredMessage)
    .transform((value, ctx) => {
      const parsed = Number.parseFloat(value);
      if (Number.isNaN(parsed)) {
        ctx.addIssue({ code: "custom", message: invalidMessage });
        return z.NEVER;
      }
      return parsed;
    });

const buildOpinionSchema = (t: Translate, scaleMin: number, scaleMax: number) =>
  z
    .object({
      position: z.string().trim().min(1, t("detail.hintPositionRequired")),
      lower: numericField(t("detail.hintFieldsRequired"), t("toast.invalidNumbers")),
      peak: numericField(t("detail.hintFieldsRequired"), t("toast.invalidNumbers")),
      upper: numericField(t("detail.hintFieldsRequired"), t("toast.invalidNumbers")),
    })
    .superRefine((data, ctx) => {
      if (data.lower > data.peak || data.peak > data.upper) {
        ctx.addIssue({
          code: "custom",
          path: ["peak"],
          message: t("toast.lowerPeakUpper"),
        });
      }
      if (data.lower < scaleMin) {
        ctx.addIssue({
          code: "custom",
          path: ["lower"],
          message: t("toast.scaleRange", { min: scaleMin, max: scaleMax }),
        });
      }
      if (data.upper > scaleMax) {
        ctx.addIssue({
          code: "custom",
          path: ["upper"],
          message: t("toast.scaleRange", { min: scaleMin, max: scaleMax }),
        });
      }
    });

type OpinionSchema = ReturnType<typeof buildOpinionSchema>;

export type OpinionFormInput = z.input<OpinionSchema>;
export type OpinionFormOutput = z.output<OpinionSchema>;
export type OpinionFormReturn = UseFormReturn<OpinionFormInput, unknown, OpinionFormOutput>;

const toFormValues = (opinion: Opinion | undefined): OpinionFormInput => ({
  position: opinion?.position ?? "",
  lower: opinion ? String(opinion.lower_bound) : "",
  peak: opinion ? String(opinion.peak) : "",
  upper: opinion ? String(opinion.upper_bound) : "",
});

/**
 * Form state for the opinion editor. Lives in the page container because the
 * desktop grid and the mobile tabs are separate subtrees: crossing the layout
 * breakpoint remounts the form component, and keeping the state here preserves
 * in-progress edits across that swap.
 */
export function useOpinionForm(
  project: ProjectWithRole | null,
  myOpinion: Opinion | undefined
): OpinionFormReturn {
  const { t } = useTranslation("projects");

  const schema = useMemo(
    () => buildOpinionSchema(t, project?.scale_min ?? 0, project?.scale_max ?? 0),
    [t, project?.scale_min, project?.scale_max]
  );

  const form = useForm<OpinionFormInput, unknown, OpinionFormOutput>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: toFormValues(myOpinion),
  });

  const { reset } = form;
  useEffect(() => {
    reset(toFormValues(myOpinion));
    // Primitive deps: opinions are re-fetched as new objects with equal values,
    // and resetting on identity change would clobber in-progress edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    reset,
    myOpinion?.position,
    myOpinion?.lower_bound,
    myOpinion?.peak,
    myOpinion?.upper_bound,
  ]);

  return form;
}
