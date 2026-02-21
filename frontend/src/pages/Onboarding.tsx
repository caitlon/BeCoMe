import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Navbar } from "@/components/layout/Navbar";
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

const steps = [
  { id: "welcome", component: StepWelcome },
  { id: "create-project", component: StepCreateProject },
  { id: "invite-experts", component: StepInviteExperts },
  { id: "enter-opinion", component: StepEnterOpinion },
  { id: "view-results", component: StepViewResults },
  { id: "complete", component: StepComplete },
];

const Onboarding = () => {
  const { t } = useTranslation("onboarding");
  const { t: tCommon } = useTranslation();
  const navigate = useNavigate();
  useDocumentTitle(tCommon("pageTitle.onboarding"));
  const [currentStep, setCurrentStep] = useState(0);
  const [direction, setDirection] = useState(0);

  const totalSteps = steps.length;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;

  const goToNext = useCallback(() => {
    /* v8 ignore next */
    if (currentStep < totalSteps - 1) {
      setDirection(1);
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep, totalSteps]);

  const goToPrevious = useCallback(() => {
    /* v8 ignore next */
    if (currentStep > 0) {
      setDirection(-1);
      setCurrentStep((prev) => prev - 1);
    }
  }, [currentStep]);

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

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Navbar />

      {/* Progress Header */}
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

      {/* Step Content */}
      <main id="main-content" className="flex-1 pt-32 pb-24 overflow-hidden">
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
              <CurrentStepComponent />
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* Navigation Footer */}
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
                    setCurrentStep(index);
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
    </div>
  );
};

export default Onboarding;
