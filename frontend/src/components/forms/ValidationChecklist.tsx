import { Check, X } from "lucide-react";

interface Requirement {
  label: string;
  met: boolean;
}

interface ValidationChecklistProps {
  title?: string;
  requirements: Requirement[];
  show?: boolean;
}

const ValidationChecklist = ({
  title,
  requirements,
  show = true,
}: ValidationChecklistProps) => {
  if (!show) return null;

  const allMet = requirements.every((req) => req.met);
  if (allMet) return null;

  return (
    <div className="mt-3 space-y-1.5">
      {title && (
        <p className="text-xs text-muted-foreground font-medium">{title}</p>
      )}
      {requirements.map((req, index) => (
        <div
          key={index}
          className={`flex items-center gap-2 text-xs ${
            req.met ? "text-success" : "text-muted-foreground"
          }`}
        >
          {req.met ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            <X className="h-3.5 w-3.5" />
          )}
          <span>{req.label}</span>
        </div>
      ))}
    </div>
  );
};

export { ValidationChecklist };
export type { Requirement };
