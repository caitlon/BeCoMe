import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { PenLine } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

export function StepEnterOpinion() {
  const { t } = useTranslation("onboarding");
  const [lower, setLower] = useState("30");
  const [peak, setPeak] = useState("50");
  const [upper, setUpper] = useState("70");

  // Fallback values form a valid triangle (0, 50, 100) when inputs are empty or invalid
  const lowerNum = parseFloat(lower) || 0;
  const peakNum = parseFloat(peak) || 50;
  const upperNum = parseFloat(upper) || 100;

  const isValid = lowerNum <= peakNum && peakNum <= upperNum;

  const scaleToX = (value: number) => {
    return 20 + ((value - 0) / 100) * 260;
  };

  return (
    <div className="flex flex-col items-center px-6 py-8">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", duration: 0.6 }}
        className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6"
      >
        <PenLine className="h-8 w-8 text-primary" />
      </motion.div>

      <motion.h2
        {...fadeInUp}
        className="font-display text-2xl md:text-3xl font-normal mb-2 text-center"
      >
        {t("steps.enterOpinion.title")}
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5 }}
        className="text-muted-foreground text-center max-w-md mb-8"
      >
        {t("steps.enterOpinion.description")}
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="w-full max-w-lg"
      >
        <Card>
          <CardContent className="pt-6 space-y-6">
            <p className="text-sm font-medium">{t("steps.enterOpinion.tryIt")}</p>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="lower-input" className="text-xs">
                  {t("steps.enterOpinion.fields.lower")}
                </Label>
                <Input
                  id="lower-input"
                  type="number"
                  value={lower}
                  onChange={(e) => setLower(e.target.value)}
                  className="mt-1 font-mono"
                  min={0}
                  max={100}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {t("steps.enterOpinion.fields.lowerHint")}
                </p>
              </div>
              <div>
                <Label htmlFor="peak-input" className="text-xs">
                  {t("steps.enterOpinion.fields.peak")}
                </Label>
                <Input
                  id="peak-input"
                  type="number"
                  value={peak}
                  onChange={(e) => setPeak(e.target.value)}
                  className="mt-1 font-mono"
                  min={0}
                  max={100}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {t("steps.enterOpinion.fields.peakHint")}
                </p>
              </div>
              <div>
                <Label htmlFor="upper-input" className="text-xs">
                  {t("steps.enterOpinion.fields.upper")}
                </Label>
                <Input
                  id="upper-input"
                  type="number"
                  value={upper}
                  onChange={(e) => setUpper(e.target.value)}
                  className="mt-1 font-mono"
                  min={0}
                  max={100}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {t("steps.enterOpinion.fields.upperHint")}
                </p>
              </div>
            </div>

            <p className="text-xs text-muted-foreground italic">
              {t("steps.enterOpinion.rule")}
            </p>

            {/* Triangle Preview */}
            <div className="bg-muted rounded-lg p-4">
              <svg
                viewBox="0 0 300 120"
                className="w-full"
                role="img"
                aria-labelledby="triangle-preview-title"
              >
                <title id="triangle-preview-title">
                  {t("steps.enterOpinion.previewTitle")}
                </title>
                {/* Axes */}
                <line
                  x1="20"
                  y1="100"
                  x2="280"
                  y2="100"
                  stroke="currentColor"
                  strokeOpacity="0.2"
                />
                <line
                  x1="20"
                  y1="100"
                  x2="20"
                  y2="20"
                  stroke="currentColor"
                  strokeOpacity="0.2"
                />

                {/* Scale labels */}
                <text
                  x="20"
                  y="115"
                  className="fill-muted-foreground"
                  fontSize="10"
                  textAnchor="middle"
                >
                  0
                </text>
                <text
                  x="150"
                  y="115"
                  className="fill-muted-foreground"
                  fontSize="10"
                  textAnchor="middle"
                >
                  50
                </text>
                <text
                  x="280"
                  y="115"
                  className="fill-muted-foreground"
                  fontSize="10"
                  textAnchor="middle"
                >
                  100
                </text>

                {/* Y axis label */}
                <text
                  x="10"
                  y="60"
                  className="fill-muted-foreground"
                  fontSize="8"
                  textAnchor="middle"
                  transform="rotate(-90, 10, 60)"
                >
                  {t("steps.enterOpinion.yAxisLabel")}
                </text>

                {isValid && (
                  <>
                    {/* Triangle */}
                    <motion.polygon
                      initial={{ opacity: 0 }}
                      animate={{
                        opacity: 1,
                        points: `${scaleToX(lowerNum)},100 ${scaleToX(peakNum)},25 ${scaleToX(upperNum)},100`,
                      }}
                      transition={{ duration: 0.3 }}
                      fill="currentColor"
                      fillOpacity="0.1"
                      stroke="hsl(var(--primary))"
                      strokeWidth="2"
                    />

                    {/* Peak marker */}
                    <motion.circle
                      cx={scaleToX(peakNum)}
                      cy={25}
                      r="4"
                      fill="hsl(var(--primary))"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.2 }}
                    />

                    {/* Value labels */}
                    <text
                      x={scaleToX(lowerNum)}
                      y="95"
                      className="fill-muted-foreground"
                      fontSize="9"
                      textAnchor="middle"
                    >
                      {lowerNum}
                    </text>
                    <text
                      x={scaleToX(peakNum)}
                      y="18"
                      className="fill-primary"
                      fontSize="9"
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      {peakNum}
                    </text>
                    <text
                      x={scaleToX(upperNum)}
                      y="95"
                      className="fill-muted-foreground"
                      fontSize="9"
                      textAnchor="middle"
                    >
                      {upperNum}
                    </text>
                  </>
                )}

                {!isValid && (
                  <text
                    x="150"
                    y="60"
                    className="fill-destructive"
                    fontSize="12"
                    textAnchor="middle"
                  >
                    {t("steps.enterOpinion.preview")}
                  </text>
                )}
              </svg>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
