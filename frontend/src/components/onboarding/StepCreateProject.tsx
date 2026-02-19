import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { FolderPlus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fadeInUp } from "@/lib/motion";
import { StepHeader } from "./StepHeader";

const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

export function StepCreateProject() {
  const { t } = useTranslation("onboarding");

  return (
    <div className="flex flex-col items-center px-6 py-8">
      <StepHeader
        icon={FolderPlus}
        titleKey="steps.createProject.title"
        descriptionKey="steps.createProject.description"
      />

      <motion.div
        variants={stagger}
        initial="initial"
        animate="animate"
        className="w-full max-w-md"
      >
        <Card>
          <CardContent className="pt-6 space-y-4">
            <motion.div variants={fadeInUp}>
              <Label>{t("steps.createProject.form.name")}</Label>
              <Input
                placeholder={t("steps.createProject.form.namePlaceholder")}
                className="mt-1"
                readOnly
              />
            </motion.div>

            <motion.div variants={fadeInUp}>
              <Label>{t("steps.createProject.form.description")}</Label>
              <Input
                placeholder={t("steps.createProject.form.descriptionPlaceholder")}
                className="mt-1"
                readOnly
              />
            </motion.div>

            <fieldset>
              <legend className="sr-only">{t("steps.createProject.form.scaleSettings")}</legend>
              <motion.div variants={fadeInUp} className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-xs">
                    {t("steps.createProject.form.scaleMin")}
                  </Label>
                  <Input
                    type="number"
                    placeholder="0"
                    className="mt-1 font-mono"
                    readOnly
                  />
                </div>
                <div>
                  <Label className="text-xs">
                    {t("steps.createProject.form.scaleMax")}
                  </Label>
                  <Input
                    type="number"
                    placeholder="100"
                    className="mt-1 font-mono"
                    readOnly
                  />
                </div>
                <div>
                  <Label className="text-xs">
                    {t("steps.createProject.form.scaleUnit")}
                  </Label>
                  <Input
                    placeholder={t("steps.createProject.form.unitPlaceholder")}
                    className="mt-1"
                    readOnly
                  />
                </div>
              </motion.div>
            </fieldset>

            <motion.p
              variants={fadeInUp}
              className="text-xs text-muted-foreground italic"
            >
              {t("steps.createProject.hint")}
            </motion.p>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
