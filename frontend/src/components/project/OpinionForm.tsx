import { useId } from "react";
import { Controller, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SubmitButton } from "@/components/forms";
import { cn } from "@/lib/utils";
import { ProjectWithRole, Opinion } from "@/types/api";
import { scaleToX, trianglePoints } from "./triangle-geometry";
import { OpinionFormOutput, OpinionFormReturn } from "./use-opinion-form";

export interface OpinionFormProps {
  form: OpinionFormReturn;
  project: ProjectWithRole;
  myOpinion?: Opinion;
  isSaving: boolean;
  onSubmit: (values: OpinionFormOutput) => Promise<void>;
  onDelete: () => void;
}

interface NumericFieldProps {
  form: OpinionFormReturn;
  name: "lower" | "peak" | "upper";
  label: string;
  placeholder?: string;
  fieldId: string;
}

const NumericField = ({ form, name, label, placeholder, fieldId }: NumericFieldProps) => {
  const error = form.formState.errors[name];
  const errorId = `${fieldId}-error`;

  return (
    <div>
      <Label htmlFor={fieldId} className="text-xs text-muted-foreground">
        {label}
      </Label>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <Input
            id={fieldId}
            type="number"
            required
            placeholder={placeholder}
            className={cn("font-mono", error && "border-destructive")}
            aria-invalid={!!error}
            aria-describedby={error ? errorId : undefined}
            {...field}
            onChange={(event) => {
              field.onChange(event);
              // The "lower <= peak <= upper" rule attaches its error to `peak`, so editing
              // any sibling must re-check the group -- otherwise a corrected value leaves a
              // stale cross-field error behind. Re-validate only the SIBLINGS already allowed
              // to show errors (touched, or every field once submitted), never the field being
              // typed into: form.trigger([name]) validates eagerly and would bypass
              // mode:"onTouched", flashing an error mid-keystroke. RHF still revalidates the
              // edited field itself through its own onTouched/reValidate path.
              const { touchedFields, isSubmitted } = form.formState;
              const group = (["lower", "peak", "upper"] as const).filter(
                (candidate) => candidate !== name && (isSubmitted || touchedFields[candidate]),
              );
              void form.trigger(group);
            }}
          />
        )}
      />
      {error && (
        <p id={errorId} className="text-xs text-destructive mt-1">
          {error.message}
        </p>
      )}
    </div>
  );
};

export const OpinionForm = ({
  form,
  project,
  myOpinion,
  isSaving,
  onSubmit,
  onDelete,
}: OpinionFormProps) => {
  const { t } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();
  const previewTitleId = useId();
  const hintId = useId();
  const fieldIdPrefix = useId();

  const { position, lower, peak, upper } = useWatch({ control: form.control });
  const positionError = form.formState.errors.position;
  const positionErrorId = `${fieldIdPrefix}-position-error`;

  const lowerNum = Number.parseFloat(lower ?? "") || 0;
  const peakNum = Number.parseFloat(peak ?? "") || 0;
  const upperNum = Number.parseFloat(upper ?? "") || 0;
  const isPreviewValid =
    lowerNum <= peakNum &&
    peakNum <= upperNum &&
    lowerNum >= project.scale_min &&
    upperNum <= project.scale_max;
  const hasChanges = !myOpinion || form.formState.isDirty;

  let hintMessage: string | null = null;
  if (!position?.trim()) {
    hintMessage = t("detail.hintPositionRequired");
  } else if (!lower || !peak || !upper) {
    hintMessage = t("detail.hintFieldsRequired");
  } else if (!hasChanges) {
    hintMessage = t("detail.hintNoChanges");
  }

  const previewScale = {
    scaleMin: project.scale_min,
    scaleMax: project.scale_max,
    x0: 10,
    width: 180,
  };

  return (
    <Card className="border-2 border-primary/20" aria-busy={isSaving}>
      <CardHeader>
        <CardTitle className="text-lg">{t("detail.yourOpinion")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="space-y-4">
          <div>
            <Label htmlFor={`${fieldIdPrefix}-position`}>{t("detail.position")}</Label>
            <Controller
              control={form.control}
              name="position"
              render={({ field }) => (
                <Input
                  id={`${fieldIdPrefix}-position`}
                  required
                  placeholder={t("detail.positionPlaceholder")}
                  className={cn(positionError && "border-destructive")}
                  aria-invalid={!!positionError}
                  aria-describedby={positionError ? positionErrorId : undefined}
                  {...field}
                />
              )}
            />
            {positionError && (
              <p id={positionErrorId} className="text-xs text-destructive mt-1">
                {positionError.message}
              </p>
            )}
          </div>

          <fieldset>
            <legend className="text-sm font-medium leading-none mb-2">{t("detail.yourEstimate")}</legend>
            <div className="grid grid-cols-3 gap-4">
              <NumericField
                form={form}
                name="lower"
                label={tFuzzy("fuzzy.lowerDesc")}
                placeholder={String(project.scale_min)}
                fieldId={`${fieldIdPrefix}-lower`}
              />
              <NumericField
                form={form}
                name="peak"
                label={tFuzzy("fuzzy.peakDesc")}
                fieldId={`${fieldIdPrefix}-peak`}
              />
              <NumericField
                form={form}
                name="upper"
                label={tFuzzy("fuzzy.upperDesc")}
                placeholder={String(project.scale_max)}
                fieldId={`${fieldIdPrefix}-upper`}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {t("detail.range")}: {project.scale_min} — {project.scale_max} {project.scale_unit}
            </p>
          </fieldset>

          {/* Mini Triangle Preview */}
          {lower && peak && upper && isPreviewValid && (
            <div className="bg-muted rounded p-4">
              <svg viewBox="0 0 200 60" className="w-full h-12" aria-labelledby={previewTitleId}>
                <title id={previewTitleId}>
                  {tFuzzy("a11y.opinionPreviewDesc", { lower: lowerNum, peak: peakNum, upper: upperNum })}
                </title>
                <line
                  x1="10"
                  y1="50"
                  x2="190"
                  y2="50"
                  stroke="currentColor"
                  strokeOpacity="0.2"
                />
                <polygon
                  points={trianglePoints(lowerNum, peakNum, upperNum, 50, 10, previewScale)}
                  fill="currentColor"
                  fillOpacity="0.1"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <text
                  x={scaleToX(lowerNum, previewScale)}
                  y="58"
                  className="fill-muted-foreground"
                  fontSize="8"
                  textAnchor="middle"
                >
                  {lowerNum}
                </text>
                <text
                  x={scaleToX(peakNum, previewScale)}
                  y="8"
                  className="fill-muted-foreground"
                  fontSize="8"
                  textAnchor="middle"
                >
                  {peakNum}
                </text>
                <text
                  x={scaleToX(upperNum, previewScale)}
                  y="58"
                  className="fill-muted-foreground"
                  fontSize="8"
                  textAnchor="middle"
                >
                  {upperNum}
                </text>
              </svg>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <div className="flex gap-3">
              <SubmitButton
                disabled={!lower || !peak || !upper || !position?.trim() || !hasChanges}
                isLoading={isSaving}
                className="flex-1"
                aria-describedby={hintMessage ? hintId : undefined}
              >
                {myOpinion ? t("detail.updateOpinion") : t("detail.saveOpinion")}
              </SubmitButton>
            </div>
            {hintMessage && (
              <p id={hintId} className="text-xs text-muted-foreground">
                {hintMessage}
              </p>
            )}
          </div>

          {myOpinion && (
            <button
              type="button"
              onClick={onDelete}
              className="text-sm text-destructive hover:underline"
            >
              {t("detail.deleteOpinion")}
            </button>
          )}
        </form>
      </CardContent>
    </Card>
  );
};
