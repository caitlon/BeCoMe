import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { DriveStep } from "driver.js";
import { useTour } from "@/hooks/useTour";
import "./tourStyles.css";

interface ProjectDetailTourProps {
  onStartTour?: (startFn: () => void) => void;
}

export function ProjectDetailTour({ onStartTour }: ProjectDetailTourProps) {
  const { t } = useTranslation("tour");

  const steps: DriveStep[] = useMemo(
    () => [
      {
        popover: {
          title: t("projectDetail.welcome.title"),
          description: t("projectDetail.welcome.description"),
        },
      },
      {
        element: '[data-tour="opinion-form"]',
        popover: {
          title: t("projectDetail.opinionForm.title"),
          description: t("projectDetail.opinionForm.description"),
          side: "right",
          align: "start",
        },
      },
      {
        element: '[data-tour="fuzzy-inputs"]',
        popover: {
          title: t("projectDetail.fuzzyValues.title"),
          description: t("projectDetail.fuzzyValues.description"),
          side: "bottom",
          align: "center",
        },
      },
      {
        element: '[data-tour="triangle-preview"]',
        popover: {
          title: t("projectDetail.preview.title"),
          description: t("projectDetail.preview.description"),
          side: "top",
          align: "center",
        },
      },
      {
        element: '[data-tour="save-button"]',
        popover: {
          title: t("projectDetail.saveButton.title"),
          description: t("projectDetail.saveButton.description"),
          side: "top",
          align: "center",
        },
      },
      {
        element: '[data-tour="other-opinions"]',
        popover: {
          title: t("projectDetail.otherOpinions.title"),
          description: t("projectDetail.otherOpinions.description"),
          side: "right",
          align: "start",
        },
      },
      {
        element: '[data-tour="results"]',
        popover: {
          title: t("projectDetail.results.title"),
          description: t("projectDetail.results.description"),
          side: "left",
          align: "start",
        },
      },
      {
        element: '[data-tour="visualization"]',
        popover: {
          title: t("projectDetail.visualization.title"),
          description: t("projectDetail.visualization.description"),
          side: "left",
          align: "start",
        },
      },
      {
        popover: {
          title: t("projectDetail.complete.title"),
          description: t("projectDetail.complete.description"),
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t]
  );

  const { startTour } = useTour({
    tourId: "projectDetail",
    steps,
    autoStart: true,
  });

  useEffect(() => {
    if (onStartTour) {
      onStartTour(startTour);
    }
  }, [onStartTour, startTour]);

  return null;
}
