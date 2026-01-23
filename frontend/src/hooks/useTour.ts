import { useCallback, useEffect, useState } from "react";
import { driver, Driver, DriveStep } from "driver.js";
import "driver.js/dist/driver.css";
import { useTranslation } from "react-i18next";

const TOUR_STORAGE_KEY = "become-tour-completed";

interface TourState {
  projectDetail: boolean;
}

function getTourState(): TourState {
  try {
    const stored = localStorage.getItem(TOUR_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch {
    // Ignore parse errors
  }
  return { projectDetail: false };
}

function setTourCompleted(tourId: keyof TourState): void {
  const state = getTourState();
  state[tourId] = true;
  localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify(state));
}

function resetTourState(tourId: keyof TourState): void {
  const state = getTourState();
  state[tourId] = false;
  localStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify(state));
}

interface UseTourOptions {
  tourId: keyof TourState;
  steps: DriveStep[];
  autoStart?: boolean;
}

interface UseTourReturn {
  startTour: () => void;
  isCompleted: boolean;
  resetTour: () => void;
  isActive: boolean;
}

export function useTour({
  tourId,
  steps,
  autoStart = true,
}: UseTourOptions): UseTourReturn {
  const { t } = useTranslation("tour");
  const [isCompleted, setIsCompleted] = useState(() => getTourState()[tourId]);
  const [isActive, setIsActive] = useState(false);
  const [driverInstance, setDriverInstance] = useState<Driver | null>(null);

  useEffect(() => {
    const instance = driver({
      showProgress: true,
      animate: true,
      allowClose: true,
      overlayColor: "rgba(0, 0, 0, 0.75)",
      stagePadding: 10,
      stageRadius: 8,
      popoverClass: "become-tour-popover",
      nextBtnText: t("buttons.next"),
      prevBtnText: t("buttons.previous"),
      doneBtnText: t("buttons.finish"),
      progressText: "{{current}} / {{total}}",
      onDestroyStarted: () => {
        setTourCompleted(tourId);
        setIsCompleted(true);
        setIsActive(false);
        instance.destroy();
      },
      steps,
    });

    setDriverInstance(instance);

    return () => {
      instance.destroy();
    };
  }, [tourId, steps, t]);

  useEffect(() => {
    if (autoStart && !isCompleted && driverInstance && steps.length > 0) {
      // Small delay to ensure DOM elements are rendered
      const timeout = setTimeout(() => {
        driverInstance.drive();
        setIsActive(true);
      }, 500);

      return () => clearTimeout(timeout);
    }
  }, [autoStart, isCompleted, driverInstance, steps.length]);

  const startTour = useCallback(() => {
    if (driverInstance) {
      driverInstance.drive();
      setIsActive(true);
    }
  }, [driverInstance]);

  const resetTour = useCallback(() => {
    resetTourState(tourId);
    setIsCompleted(false);
  }, [tourId]);

  return {
    startTour,
    isCompleted,
    resetTour,
    isActive,
  };
}
