import { Check, X } from "lucide-react";
import { useTranslation } from "react-i18next";

interface Requirement {
  label: string;
  met: boolean;
}

interface ValidationChecklistProps {
  id?: string;
  title?: string;
  requirements: Requirement[];
  show?: boolean;
}

const ValidationChecklist = ({
  id,
  title,
  requirements,
  show = true,
}: ValidationChecklistProps) => {
  const { t } = useTranslation("common");

  if (!show) return null;

  const allMet = requirements.every((req) => req.met);
  if (allMet) return null;

  return (
    <div id={id} className="mt-3 space-y-1.5">
      {title && (
        <p className="text-xs text-muted-foreground font-medium">{title}</p>
      )}
      {requirements.map((req) => (
        <div
          key={req.label}
          className={`flex items-center gap-2 text-xs ${
            req.met ? "text-success" : "text-muted-foreground"
          }`}
        >
          {req.met ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            <X className="h-3.5 w-3.5" />
          )}
          <span>{req.label}</span>{" "}
          <span className="sr-only">
            {req.met ? t("a11y.requirementMet") : t("a11y.requirementNotMet")}
          </span>
        </div>
      ))}
    </div>
  );
};

export { ValidationChecklist };
export type { Requirement };
