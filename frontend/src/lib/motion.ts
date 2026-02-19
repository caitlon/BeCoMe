/**
 * Shared framer-motion animation presets.
 */

/** Fade-in with upward slide. Works as both direct props and variant. */
export const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
} as const;
