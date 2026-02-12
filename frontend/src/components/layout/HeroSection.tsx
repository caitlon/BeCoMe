import { motion } from "framer-motion";

interface HeroSectionProps {
  title: string;
  subtitle: string;
}

export function HeroSection({ title, subtitle }: HeroSectionProps) {
  return (
    <section className="pt-24 pb-12 md:pt-32 md:pb-16 bg-secondary/30">
      <div className="container mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-3xl mx-auto"
        >
          <h1 className="font-display text-3xl md:text-5xl font-normal mb-4">
            {title}
          </h1>
          <p className="text-lg text-muted-foreground">{subtitle}</p>
        </motion.div>
      </div>
    </section>
  );
}
