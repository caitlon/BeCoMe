import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  readonly title: string;
  readonly description?: string;
  /** Meta row under the description — badges, actions, a back link. */
  readonly children?: React.ReactNode;
  readonly className?: string;
}

/**
 * The h1 block for pages inside the app. Public pages use HeroSection instead,
 * which carries the larger marketing scale and its own tinted band.
 */
export function PageHeader({ title, description, children, className }: PageHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("mb-8", className)}
    >
      <h1 className={cn("text-app-title", description || children ? "mb-2" : undefined)}>
        {title}
      </h1>
      {description && <p className="text-muted-foreground mb-4">{description}</p>}
      {children}
    </motion.div>
  );
}
