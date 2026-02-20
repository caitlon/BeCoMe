import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import type { LucideIcon } from "lucide-react";
import { fadeInUp } from "@/lib/motion";

interface StepHeaderProps {
  readonly icon: LucideIcon;
  readonly titleKey: string;
  readonly descriptionKey: string;
}

export function StepHeader({ icon: Icon, titleKey, descriptionKey }: StepHeaderProps) {
  const { t } = useTranslation("onboarding");

  return (
    <>
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", duration: 0.6 }}
        className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6"
      >
        <Icon className="h-8 w-8 text-primary" />
      </motion.div>

      <motion.h2
        {...fadeInUp}
        className="font-display text-2xl md:text-3xl font-normal mb-2 text-center"
      >
        {t(titleKey)}
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5 }}
        className="text-muted-foreground text-center max-w-md mb-8"
      >
        {t(descriptionKey)}
      </motion.p>
    </>
  );
}
