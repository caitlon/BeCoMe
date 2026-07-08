import { useId } from "react";
import { useTranslation } from "react-i18next";
import { ProjectWithRole, Opinion, CalculationResult } from "@/types/api";
import { scaleToX as scaleToXHelper, trianglePoints, type TriangleScale } from "./triangle-geometry";

export interface TriangleVisualizationProps {
  result: CalculationResult;
  project: ProjectWithRole;
  showIndividual: boolean;
  opinions: Opinion[];
}

export const TriangleVisualization = ({
  result,
  project,
  showIndividual,
  opinions,
}: TriangleVisualizationProps) => {
  const { t: tCommon } = useTranslation();
  const resultsTitleId = useId();

  const scale: TriangleScale = {
    scaleMin: project.scale_min,
    scaleMax: project.scale_max,
    x0: 40,
    width: 320,
  };
  const scaleToX = (value: number) => scaleToXHelper(value, scale);

  const baseY = 160;
  const peakY = 30;

  return (
    <svg viewBox="0 0 400 200" className="w-full" aria-labelledby={resultsTitleId}>
      <title id={resultsTitleId}>{tCommon("a11y.resultsChartDesc")}</title>
      {/* Axes */}
      <line
        x1="40"
        y1={baseY}
        x2="360"
        y2={baseY}
        stroke="currentColor"
        strokeOpacity="0.2"
      />
      <line
        x1="40"
        y1={baseY}
        x2="40"
        y2="20"
        stroke="currentColor"
        strokeOpacity="0.2"
      />

      {/* Scale labels */}
      <text
        x="40"
        y={baseY + 15}
        className="fill-muted-foreground"
        fontSize="10"
        textAnchor="middle"
      >
        {project.scale_min}
      </text>
      <text
        x="360"
        y={baseY + 15}
        className="fill-muted-foreground"
        fontSize="10"
        textAnchor="middle"
      >
        {project.scale_max}
      </text>

      {/* Individual opinions */}
      {showIndividual &&
        opinions.map((op) => (
          <polygon
            key={op.id}
            points={trianglePoints(op.lower_bound, op.peak, op.upper_bound, baseY, peakY + 20, scale)}
            fill="currentColor"
            fillOpacity="0.05"
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="1"
          />
        ))}

      {/* Arithmetic Mean */}
      <polygon
        points={trianglePoints(
          result.arithmetic_mean.lower,
          result.arithmetic_mean.peak,
          result.arithmetic_mean.upper,
          baseY,
          peakY + 10,
          scale,
        )}
        fill="hsl(var(--chart-mean))"
        fillOpacity="0.1"
        stroke="hsl(var(--chart-mean))"
        strokeWidth="1.5"
        strokeDasharray="4,4"
      />

      {/* Median */}
      <polygon
        points={trianglePoints(
          result.median.lower,
          result.median.peak,
          result.median.upper,
          baseY,
          peakY + 10,
          scale,
        )}
        fill="hsl(var(--chart-median))"
        fillOpacity="0.1"
        stroke="hsl(var(--chart-median))"
        strokeWidth="1.5"
        strokeDasharray="4,4"
      />

      {/* Best Compromise - Black/White (theme-aware) */}
      <polygon
        points={trianglePoints(
          result.best_compromise.lower,
          result.best_compromise.peak,
          result.best_compromise.upper,
          baseY,
          peakY,
          scale,
        )}
        fill="currentColor"
        fillOpacity="0.1"
        stroke="currentColor"
        strokeWidth="2"
      />

      {/* Centroid marker */}
      <line
        x1={scaleToX(result.best_compromise.centroid)}
        y1={baseY}
        x2={scaleToX(result.best_compromise.centroid)}
        y2={baseY - 40}
        stroke="currentColor"
        strokeWidth="1"
        strokeDasharray="2,2"
      />
      <circle
        cx={scaleToX(result.best_compromise.centroid)}
        cy={baseY - 45}
        r="3"
        fill="currentColor"
      />
    </svg>
  );
};
