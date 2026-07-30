import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import { fadeInUp } from "@/lib/motion";

interface HeroSectionProps {
  readonly title: string;
  readonly subtitle: string;
  /**
   * "center" keeps the heading block centred, which suits a long-form reading
   * column (About). "left" matches the flush-left headings on Docs and FAQ.
   */
  readonly align?: "left" | "center";
  /**
   * "compact" trims the bottom padding for pages that open straight into a
   * sidebar layout rather than a full-width first section.
   */
  readonly spacing?: "default" | "compact";
}

const SPACING_CLASSES = {
  default: "pt-24 pb-12 md:pt-32 md:pb-16",
  compact: "pt-24 pb-8 md:pt-32 md:pb-12",
} as const;

export function HeroSection({
  title,
  subtitle,
  align = "center",
  spacing = "default",
}: HeroSectionProps) {
  return (
    <section className={cn(SPACING_CLASSES[spacing], "bg-secondary/30")}>
      <div className="container mx-auto px-6">
        <motion.div {...fadeInUp} className={cn("max-w-3xl", align === "center" && "mx-auto")}>
          <h1 className="text-page-title mb-4">{title}</h1>
          <p className="text-lg text-muted-foreground">{subtitle}</p>
        </motion.div>
      </div>
    </section>
  );
}
