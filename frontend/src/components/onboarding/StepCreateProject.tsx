import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { FolderPlus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

export function StepCreateProject() {
  const { t } = useTranslation("onboarding");

  return (
    <div className="flex flex-col items-center px-6 py-8">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", duration: 0.6 }}
        className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6"
      >
        <FolderPlus className="h-8 w-8 text-primary" />
      </motion.div>

      <motion.h2
        {...fadeInUp}
        className="font-display text-2xl md:text-3xl font-normal mb-2 text-center"
      >
        {t("steps.createProject.title")}
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5 }}
        className="text-muted-foreground text-center max-w-md mb-8"
      >
        {t("steps.createProject.description")}
      </motion.p>

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
