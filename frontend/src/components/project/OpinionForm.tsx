import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SubmitButton } from "@/components/forms";
import { ProjectWithRole, Opinion } from "@/types/api";
import { scaleToX, trianglePoints } from "./triangle-geometry";

export interface OpinionFormProps {
  position: string;
  setPosition: (v: string) => void;
  lower: string;
  setLower: (v: string) => void;
  peak: string;
  setPeak: (v: string) => void;
  upper: string;
  setUpper: (v: string) => void;
  project: ProjectWithRole;
  myOpinion?: Opinion;
  isSaving: boolean;
  onSave: () => void;
  onDelete: () => void;
}

export const OpinionForm = ({
  position,
  setPosition,
  lower,
  setLower,
  peak,
  setPeak,
  upper,
  setUpper,
  project,
  myOpinion,
  isSaving,
  onSave,
  onDelete,
}: OpinionFormProps) => {
  const { t } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();
  const previewTitleId = useId();
  const hintId = useId();
  const lowerNum = Number.parseFloat(lower) || 0;
  const peakNum = Number.parseFloat(peak) || 0;
  const upperNum = Number.parseFloat(upper) || 0;
  const isValid =
    lowerNum <= peakNum &&
    peakNum <= upperNum &&
    lowerNum >= project.scale_min &&
    upperNum <= project.scale_max;
  const hasChanges = !myOpinion ||
    position !== (myOpinion.position || "") ||
    lower !== String(myOpinion.lower_bound) ||
    peak !== String(myOpinion.peak) ||
    upper !== String(myOpinion.upper_bound);

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
      <CardContent className="space-y-4">
        <div>
          <Label htmlFor="position">{t("detail.position")}</Label>
          <Input
            id="position"
            required
            placeholder={t("detail.positionPlaceholder")}
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
        </div>

        <fieldset>
          <legend className="text-sm font-medium leading-none mb-2">{t("detail.yourEstimate")}</legend>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="opinion-lower" className="text-xs text-muted-foreground">
                {tFuzzy("fuzzy.lowerDesc")}
              </Label>
              <Input
                id="opinion-lower"
                type="number"
                required
                placeholder={String(project.scale_min)}
                value={lower}
                onChange={(e) => setLower(e.target.value)}
                className="font-mono"
              />
            </div>
            <div>
              <Label htmlFor="opinion-peak" className="text-xs text-muted-foreground">
                {tFuzzy("fuzzy.peakDesc")}
              </Label>
              <Input
                id="opinion-peak"
                type="number"
                required
                value={peak}
                onChange={(e) => setPeak(e.target.value)}
                className="font-mono"
              />
            </div>
            <div>
              <Label htmlFor="opinion-upper" className="text-xs text-muted-foreground">
                {tFuzzy("fuzzy.upperDesc")}
              </Label>
              <Input
                id="opinion-upper"
                type="number"
                required
                placeholder={String(project.scale_max)}
                value={upper}
                onChange={(e) => setUpper(e.target.value)}
                className="font-mono"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {t("detail.range")}: {project.scale_min} — {project.scale_max} {project.scale_unit}
          </p>
        </fieldset>

        {/* Mini Triangle Preview */}
        {lower && peak && upper && isValid && (
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
          {(() => {
            let hintMessage: string | null = null;
            if (!position.trim()) {
              hintMessage = t("detail.hintPositionRequired");
            } else if (!lower || !peak || !upper) {
              hintMessage = t("detail.hintFieldsRequired");
            } else if (!hasChanges) {
              hintMessage = t("detail.hintNoChanges");
            }

            return (
              <>
                <div className="flex gap-3">
                  <SubmitButton
                    type="button"
                    onClick={onSave}
                    disabled={!lower || !peak || !upper || !position.trim() || !hasChanges}
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
              </>
            );
          })()}
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
      </CardContent>
    </Card>
  );
};
