import { useId } from "react";
import { useTranslation } from "react-i18next";
import { ProjectWithRole, Opinion, CalculationResult } from "@/types/api";
import { scaleToX as scaleToXHelper, type TriangleScale } from "./triangle-geometry";

export interface OpinionLandscapeProps {
  result: CalculationResult;
  project: ProjectWithRole;
  opinions: Opinion[];
}

export const OpinionLandscape = ({ result, project, opinions }: OpinionLandscapeProps) => {
  const { t } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();
  const titleId = useId();
  const descId = useId();

  const scale: TriangleScale = {
    scaleMin: project.scale_min,
    scaleMax: project.scale_max,
    x0: 40,
    width: 320,
  };
  const scaleToX = (value: number) => scaleToXHelper(value, scale);

  const axisY = 55;
  const bestX = scaleToX(result.best_compromise.centroid);
  const meanX = scaleToX(result.arithmetic_mean.centroid);
  const medianX = scaleToX(result.median.centroid);

  const centroids = opinions.map((op) => op.centroid);
  const description = opinions.length > 0
    ? tFuzzy("landscapeChart.srSummary", {
        count: opinions.length,
        min: Math.min(...centroids).toFixed(2),
        max: Math.max(...centroids).toFixed(2),
        compromise: result.best_compromise.centroid.toFixed(2),
      })
    : tFuzzy("landscapeChart.srSummaryEmpty", {
        compromise: result.best_compromise.centroid.toFixed(2),
      });

  return (
    <div>
      <svg
        viewBox="0 0 400 100"
        className="w-full"
        role="img"
        aria-labelledby={titleId}
        aria-describedby={descId}
      >
        <title id={titleId}>{tFuzzy("a11y.landscapeChartDesc")}</title>
        <desc id={descId}>{description}</desc>

        {/* Axis */}
        <line
          x1="40"
          y1={axisY}
          x2="360"
          y2={axisY}
          stroke="currentColor"
          strokeOpacity="0.2"
        />

        {/* Scale end labels */}
        <text
          x="40"
          y={axisY + 25}
          className="fill-muted-foreground"
          fontSize="10"
          textAnchor="middle"
        >
          {project.scale_min}
        </text>
        <text
          x="360"
          y={axisY + 25}
          className="fill-muted-foreground"
          fontSize="10"
          textAnchor="middle"
        >
          {project.scale_max}
        </text>

        {/* Individual expert opinions */}
        {opinions.map((op) => (
          <circle
            key={op.id}
            data-testid="opinion-dot"
            cx={scaleToX(op.centroid)}
            cy={axisY}
            r="4"
            className="fill-muted-foreground"
            fillOpacity="0.5"
          />
        ))}

        {/* Arithmetic Mean (Gamma) */}
        <line
          x1={meanX}
          y1={axisY - 10}
          x2={meanX}
          y2={axisY + 10}
          stroke="hsl(var(--chart-mean))"
          strokeWidth="2"
        />

        {/* Median (Omega) */}
        <line
          x1={medianX}
          y1={axisY - 10}
          x2={medianX}
          y2={axisY + 10}
          stroke="hsl(var(--chart-median))"
          strokeWidth="2"
        />

        {/* Best Compromise */}
        <line
          x1={bestX}
          y1={axisY - 22}
          x2={bestX}
          y2={axisY + 18}
          stroke="hsl(var(--primary))"
          strokeWidth="2.5"
        />
        <circle
          data-testid="landscape-best-marker"
          cx={bestX}
          cy={axisY}
          r="5"
          fill="hsl(var(--primary))"
        />
        <text
          data-testid="landscape-best-label"
          x={bestX}
          y={axisY - 28}
          className="fill-primary"
          fontSize="11"
          textAnchor="middle"
        >
          {`${tFuzzy("fuzzy.best")} ${result.best_compromise.centroid.toFixed(2)} ± ${result.max_error.toFixed(2)}`}
        </text>
      </svg>

      {/* Legend */}
      <div className="flex gap-4 text-xs justify-center flex-wrap mt-3">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-muted-foreground/50" />
          <span>{t("detail.expert")}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-chart-mean" />
          <span>{tFuzzy("fuzzy.mean")}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-chart-median" />
          <span>{tFuzzy("fuzzy.median")}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-primary" />
          <span>{tFuzzy("fuzzy.best")}</span>
        </div>
      </div>
    </div>
  );
};
