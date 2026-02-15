import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ReferenceLine,
  Tooltip,
} from "recharts";
import {
  ChartContainer,
  type ChartConfig,
} from "@/components/ui/chart";
import type { Opinion, CalculationResult } from "@/types/api";

interface CentroidBarChartProps {
  readonly opinions: Opinion[];
  readonly result: CalculationResult;
}

interface ChartDataItem {
  x: number;
  y: number;
  centroid: number;
  lower: number;
  peak: number;
  upper: number;
  fullName: string;
  position: string;
}

function CustomTooltip({
  active,
  payload,
  tChart,
  tFuzzy,
}: {
  readonly active?: boolean;
  readonly payload?: Array<{ payload: ChartDataItem }>;
  readonly tChart: (key: string) => string;
  readonly tFuzzy: (key: string) => string;
}) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;

  return (
    <div className="rounded-lg border border-border/50 bg-background px-3 py-2 text-xs shadow-xl" role="tooltip">
      <div className="font-medium">{data.fullName}</div>
      {data.position && (
        <div className="text-muted-foreground">{data.position}</div>
      )}
      <div className="mt-1.5 space-y-0.5 font-mono">
        <div>
          {tFuzzy("fuzzy.lower")}: {data.lower.toFixed(2)} | {tFuzzy("fuzzy.peak")}: {data.peak.toFixed(2)} | {tFuzzy("fuzzy.upper")}: {data.upper.toFixed(2)}
        </div>
        <div className="font-medium">
          {tChart("centroidChart.centroidValue")}: {data.centroid.toFixed(2)}
        </div>
      </div>
    </div>
  );
}

function usePrefersReducedMotion(): boolean {
  if (typeof globalThis === "undefined") return false;
  return globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function CentroidBarChart({ opinions, result }: CentroidBarChartProps) {
  const { t: tCommon } = useTranslation();
  const prefersReducedMotion = usePrefersReducedMotion();

  const chartData = useMemo(() => {
    const sorted = [...opinions].sort((a, b) => a.centroid - b.centroid);
    return sorted.map((op): ChartDataItem => ({
      x: Number.parseFloat(op.centroid.toFixed(2)),
      y: 1,
      centroid: Number.parseFloat(op.centroid.toFixed(2)),
      lower: op.lower_bound,
      peak: op.peak,
      upper: op.upper_bound,
      fullName: `${op.user_first_name} ${op.user_last_name ?? ""}`.trim(),
      position: op.position,
    }));
  }, [opinions]);

  const chartConfig: ChartConfig = {
    centroid: {
      label: tCommon("centroidChart.centroidValue"),
      color: "hsl(var(--primary))",
    },
    mean: {
      label: tCommon("centroidChart.meanLine"),
      color: "rgb(59, 130, 246)",
    },
    median: {
      label: tCommon("centroidChart.medianLine"),
      color: "rgb(34, 197, 94)",
    },
    compromise: {
      label: tCommon("centroidChart.compromiseLine"),
      theme: { light: "rgb(0, 0, 0)", dark: "rgb(255, 255, 255)" },
    },
  };

  const minCentroid = chartData[0]?.x ?? 0;
  const maxCentroid = chartData[chartData.length - 1]?.x ?? 100;
  const range = maxCentroid - minCentroid;
  const padding = range * 0.15 || 5;

  const meanC = result.arithmetic_mean.centroid;
  const medianC = result.median.centroid;
  const compromiseC = result.best_compromise.centroid;

  return (
    <figure aria-label={tCommon("a11y.centroidChartDesc")}>
      <p className="sr-only">
        {tCommon("centroidChart.srSummary", {
          count: chartData.length,
          min: chartData[0]?.centroid,
          max: chartData[chartData.length - 1]?.centroid,
          mean: meanC.toFixed(2),
          median: medianC.toFixed(2),
          compromise: compromiseC.toFixed(2),
        })}
      </p>
      <ChartContainer config={chartConfig} className="h-[120px] w-full aspect-auto!">
        <ScatterChart
          margin={{ top: 12, right: 20, left: 20, bottom: 0 }}
          accessibilityLayer
        >
          <XAxis
            type="number"
            dataKey="x"
            domain={[minCentroid - padding, maxCentroid + padding]}
            tickLine={false}
            fontSize={11}
            tickFormatter={(v: number) => v % 1 === 0 ? String(v) : v.toFixed(1)}
          />

          <YAxis
            type="number"
            dataKey="y"
            hide
            domain={[0.4, 1.6]}
          />

          <Tooltip
            content={
              <CustomTooltip
                tChart={tCommon}
                tFuzzy={tCommon}
              />
            }
          />

          <ReferenceLine
            x={meanC}
            stroke="var(--color-mean)"
            strokeDasharray="6 3"
            strokeWidth={2}
          />

          <ReferenceLine
            x={medianC}
            stroke="var(--color-median)"
            strokeDasharray="6 3"
            strokeWidth={2}
          />

          <ReferenceLine
            x={compromiseC}
            stroke="var(--color-compromise)"
            strokeDasharray="6 3"
            strokeWidth={2}
          />

          <Scatter
            data={chartData}
            fill="var(--color-centroid)"
            fillOpacity={0.7}
            isAnimationActive={!prefersReducedMotion}
          />
        </ScatterChart>
      </ChartContainer>

      <div className="flex gap-x-5 gap-y-1 text-xs mt-2 justify-center flex-wrap" aria-hidden="true">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full opacity-70" style={{ backgroundColor: "hsl(var(--primary))" }} />
          <span>{tCommon("centroidChart.centroidValue")}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-0.5 w-3" style={{ borderTop: "2px dashed rgb(59, 130, 246)" }} />
          <span>{tCommon("centroidChart.meanLine")} ({meanC.toFixed(1)})</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-0.5 w-3" style={{ borderTop: "2px dashed rgb(34, 197, 94)" }} />
          <span>{tCommon("centroidChart.medianLine")} ({medianC.toFixed(1)})</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-0.5 w-3 border-t-2 border-dashed border-foreground" />
          <span>{tCommon("centroidChart.compromiseLine")} ({compromiseC.toFixed(1)})</span>
        </div>
      </div>
    </figure>
  );
}
