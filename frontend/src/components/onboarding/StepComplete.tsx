import { useMemo } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Rocket } from "lucide-react";

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

export function StepComplete() {
  const { t } = useTranslation("onboarding");

  // Memoize particle positions to prevent recalculation on every render
  const particlePositions = useMemo(
    () =>
      [...Array(6)].map(() => ({
        x: 50 + (Math.random() - 0.5) * 60,
        y: 50 + (Math.random() - 0.5) * 60,
      })),
    []
  );

  return (
    <div className="flex flex-col items-center justify-center text-center px-6 py-12">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", duration: 0.8, bounce: 0.5 }}
        className="relative mb-8"
      >
        <div className="w-24 h-24 rounded-full bg-green-500/10 flex items-center justify-center">
          <CheckCircle2 className="h-12 w-12 text-green-500" />
        </div>
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.4 }}
          className="absolute -top-2 -right-2 w-10 h-10 rounded-full bg-primary flex items-center justify-center"
        >
          <Rocket className="h-5 w-5 text-primary-foreground" />
        </motion.div>
      </motion.div>

      <motion.h1
        {...fadeInUp}
        className="font-display text-3xl md:text-4xl font-normal mb-4"
      >
        {t("steps.complete.title")}
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="text-muted-foreground max-w-md mb-8"
      >
        {t("steps.complete.description")}
      </motion.p>

      {/* Celebration particles */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {particlePositions.map((pos, i) => (
          <motion.div
            key={i}
            initial={{
              opacity: 0,
              scale: 0,
              x: "50%",
              y: "50%",
            }}
            animate={{
              opacity: [0, 1, 0],
              scale: [0, 1, 0.5],
              x: `${pos.x}%`,
              y: `${pos.y}%`,
            }}
            transition={{
              delay: 0.5 + i * 0.1,
              duration: 1.5,
              ease: "easeOut",
            }}
            className="absolute w-3 h-3 rounded-full"
            style={{
              backgroundColor: ["#10b981", "#3b82f6", "#f59e0b", "#ec4899"][
                i % 4
              ],
            }}
          />
        ))}
      </div>
    </div>
  );
}
