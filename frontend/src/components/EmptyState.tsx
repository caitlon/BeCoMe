import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  readonly icon: LucideIcon;
  readonly title: string;
  readonly description: string;
  /** Call to action. Omit where there is nothing for the user to do yet. */
  readonly children?: React.ReactNode;
}

/** The "nothing here yet" block shown in place of a list or grid. */
export function EmptyState({ icon: Icon, title, description, children }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="text-center py-16"
    >
      <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
        <Icon className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="font-display font-medium text-lg mb-2">{title}</h3>
      <p className={`text-muted-foreground${children ? " mb-6" : ""}`}>{description}</p>
      {children}
    </motion.div>
  );
}
