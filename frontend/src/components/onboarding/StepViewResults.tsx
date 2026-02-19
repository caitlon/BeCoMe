import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { BarChart3, TrendingUp, AlertCircle, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fadeInUp } from "@/lib/motion";
import { StepHeader } from "./StepHeader";

const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.15,
    },
  },
};

export function StepViewResults() {
  const { t } = useTranslation("onboarding");

  return (
    <div className="flex flex-col items-center px-6 py-8">
      <StepHeader
        icon={BarChart3}
        titleKey="steps.viewResults.title"
        descriptionKey="steps.viewResults.description"
      />

      <motion.div
        variants={stagger}
        initial="initial"
        animate="animate"
        className="w-full max-w-lg space-y-4"
      >
        {/* Best Compromise */}
        <motion.div variants={fadeInUp}>
          <Card className="border-2 border-primary">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                {t("steps.viewResults.metrics.bestCompromise")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {t("steps.viewResults.metrics.bestCompromiseDesc")}
                </p>
                <div className="text-right">
                  <div className="font-mono text-2xl font-bold">54.3</div>
                  <div className="text-xs text-muted-foreground">
                    (42.1 | 54.3 | 68.7)
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <div className="grid grid-cols-2 gap-4">
          {/* Max Error */}
          <motion.div variants={fadeInUp}>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlertCircle className="h-4 w-4" />
                  {t("steps.viewResults.metrics.maxError")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="font-mono text-xl font-bold">8.2</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {t("steps.viewResults.metrics.maxErrorDesc")}
                </p>
              </CardContent>
            </Card>
          </motion.div>

          {/* Experts */}
          <motion.div variants={fadeInUp}>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  {t("steps.viewResults.metrics.experts")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="font-mono text-xl font-bold">12</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {t("steps.viewResults.metrics.expertsDesc")}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        <motion.p
          variants={fadeInUp}
          className="text-xs text-muted-foreground italic text-center"
        >
          {t("steps.viewResults.hint")}
        </motion.p>
      </motion.div>
    </div>
  );
}
