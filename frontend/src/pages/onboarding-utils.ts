export function getStepIndicatorClass(index: number, currentStep: number): string {
  if (index === currentStep) return "bg-primary w-6";
  if (index < currentStep) return "bg-primary/50 w-2";
  return "bg-muted-foreground/30 w-2";
}

export const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 300 : -300,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction < 0 ? 300 : -300,
    opacity: 0,
  }),
};
