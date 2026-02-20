import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { fadeInUp } from "@/lib/motion";

export function StepWelcome() {
  const { t } = useTranslation("onboarding");

  return (
    <div className="flex flex-col items-center justify-center text-center px-6 py-12">
      <motion.div
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ type: "spring", duration: 0.8 }}
        className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-8"
      >
        <Sparkles className="h-10 w-10 text-primary" />
      </motion.div>

      <motion.h1
        {...fadeInUp}
        className="font-display text-3xl md:text-4xl font-normal mb-2"
      >
        {t("steps.welcome.title")}
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5 }}
        className="text-lg text-primary font-medium mb-4"
      >
        {t("steps.welcome.subtitle")}
      </motion.p>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="text-muted-foreground max-w-md"
      >
        {t("steps.welcome.description")}
      </motion.p>
    </div>
  );
}
