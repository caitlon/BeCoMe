import { useState, useCallback, useEffect, useMemo } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { PageShell } from "@/components/layout/PageShell";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useAssistantGuide } from "@/components/assistant";
import {
  StepWelcome,
  StepCreateProject,
  StepInviteExperts,
  StepEnterOpinion,
  StepViewResults,
  StepComplete,
} from "@/components/onboarding";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { getStepIndicatorClass, slideVariants } from "@/pages/onboarding-utils";

const stepsBeforeAssistant = [
  { id: "welcome", component: StepWelcome },
  { id: "create-project", component: StepCreateProject },
  { id: "invite-experts", component: StepInviteExperts },
  { id: "enter-opinion", component: StepEnterOpinion },
  { id: "view-results", component: StepViewResults },
];
const completeStep = { id: "complete", component: StepComplete };

const Onboarding = () => {
  const { t } = useTranslation("onboarding");
  const { t: tCommon } = useTranslation();
  const navigate = useNavigate();
  useDocumentTitle(tCommon("pageTitle.onboarding"));

  // The assistant step waits for the guide module, so a build without the flag, a failed load and a
  // render error in the step all leave the six steps below.
  const loadedGuide = useAssistantGuide();
  const [guideFailed, setGuideFailed] = useState(false);
  const guide = guideFailed ? null : loadedGuide;
  const dropGuide = useCallback(() => setGuideFailed(true), []);
  const steps = useMemo(
    () => [
      ...stepsBeforeAssistant,
      ...(guide ? [{ id: "assistant", component: guide.AssistantTourStep }] : []),
      completeStep,
    ],
    [guide],
  );

  // The position is kept as a step id, not an index, because the list can grow after the first paint
  // (the module resolves) or shrink (the step throws): an index would slide onto a neighbouring step.
  // A dropped step is only ever the one on screen, so the fallback is the last step, "complete".
  const [currentId, setCurrentId] = useState(steps[0].id);
  const [direction, setDirection] = useState(0);

  const currentIndex = steps.findIndex((step) => step.id === currentId);
  const currentStep = currentIndex === -1 ? steps.length - 1 : currentIndex;
  const totalSteps = steps.length;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;

  const goToNext = useCallback(() => {
    /* v8 ignore next */
    if (currentStep < totalSteps - 1) {
      setDirection(1);
      setCurrentId(steps[currentStep + 1].id);
    }
  }, [currentStep, totalSteps, steps]);

  const goToPrevious = useCallback(() => {
    /* v8 ignore next */
    if (currentStep > 0) {
      setDirection(-1);
      setCurrentId(steps[currentStep - 1].id);
    }
  }, [currentStep, steps]);

  const navigateToProjects = useCallback(() => {
    navigate("/projects");
  }, [navigate]);

  // Keyboard navigation (skip when focus is in input/textarea/select)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.isContentEditable ||
          ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
      ) {
        return;
      }

      if (e.key === "ArrowRight" && !isLastStep) {
        e.preventDefault();
        goToNext();
      } else if (e.key === "ArrowLeft" && !isFirstStep) {
        e.preventDefault();
        goToPrevious();
      } else if (e.key === "Escape") {
        e.preventDefault();
        navigateToProjects();
      }
    };

    globalThis.addEventListener("keydown", handleKeyDown);
    return () => globalThis.removeEventListener("keydown", handleKeyDown);
  }, [goToNext, goToPrevious, navigateToProjects, isFirstStep, isLastStep]);

  const CurrentStepComponent = steps[currentStep].component;
  const currentStepContent = <CurrentStepComponent />;

  return (
    <PageShell
      variant="content"
      mainClassName="flex-1 pt-32 pb-24 overflow-hidden"
      beforeMain={
        /* Progress Header */
        <div className="fixed top-16 left-0 right-0 z-40 bg-background/95 backdrop-blur-sm border-b">
          <div className="container mx-auto px-6 py-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">
                {t("progress", { current: currentStep + 1, total: totalSteps })}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={navigateToProjects}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4 mr-1" />
                {t("buttons.skip")}
              </Button>
            </div>
            <Progress
              value={((currentStep + 1) / totalSteps) * 100}
              className="h-1"
              aria-label={t("progress", { current: currentStep + 1, total: totalSteps })}
            />
          </div>
        </div>
      }
      afterMain={
        /* Navigation Footer */
        <div className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-sm border-t">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                onClick={goToPrevious}
                disabled={isFirstStep}
                className="gap-2"
              >
                <ChevronLeft className="h-4 w-4" />
                {t("buttons.previous")}
              </Button>

              {/* Step indicators */}
              <nav aria-label={tCommon("a11y.stepNavigation")} className="hidden sm:flex items-center gap-1">
                {steps.map((step, index) => (
                  <button
                    key={step.id}
                    type="button"
                    onClick={() => {
                      setDirection(index > currentStep ? 1 : -1);
                      setCurrentId(step.id);
                    }}
                    className="p-2 rounded-full"
                    aria-label={t("buttons.goToStep", { step: index + 1 })}
                    aria-current={index === currentStep ? "step" : undefined}
                  >
                    <span className={`block h-2 rounded-full transition-all ${getStepIndicatorClass(index, currentStep)}`} />
                  </button>
                ))}
              </nav>

              {isLastStep ? (
                <Button onClick={navigateToProjects} className="gap-2">
                  {t("buttons.finish")}
                  <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button onClick={goToNext} className="gap-2">
                  {isFirstStep ? t("buttons.getStarted") : t("buttons.next")}
                  <ChevronRight className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>
      }
    >
        <div className="container mx-auto px-6 h-full">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={steps[currentStep].id}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{
                x: { type: "spring", stiffness: 300, damping: 30 },
                opacity: { duration: 0.2 },
              }}
              className="h-full"
            >
              {steps[currentStep].id === "assistant" ? (
                <ErrorBoundary fallback={null} onError={dropGuide}>
                  {currentStepContent}
                </ErrorBoundary>
              ) : (
                currentStepContent
              )}
            </motion.div>
          </AnimatePresence>
        </div>
    </PageShell>
  );
};

export default Onboarding;
