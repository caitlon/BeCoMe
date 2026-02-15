import * as React from "react";
import { FieldError } from "react-hook-form";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface FormFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: FieldError;
  description?: string;
}

function getDescribedBy(error: FieldError | undefined, errorId: string, description: string | undefined, descriptionId: string): string | undefined {
  if (error) return errorId;
  if (description) return descriptionId;
  return undefined;
}

const FormField = React.forwardRef<HTMLInputElement, FormFieldProps>(
  ({ label, error, description, id, className, name, ...props }, ref) => {
    const reactId = React.useId();
    const fieldId = id ?? name ?? reactId;
    const errorId = `${fieldId}-error`;
    const descriptionId = `${fieldId}-description`;

    return (
      <div className="space-y-2">
        <Label htmlFor={fieldId}>{label}</Label>
        <Input
          ref={ref}
          id={fieldId}
          name={name}
          aria-describedby={getDescribedBy(error, errorId, description, descriptionId)}
          aria-invalid={!!error}
          className={cn(error && "border-destructive", className)}
          {...props}
        />
        {description && !error && (
          <p id={descriptionId} className="text-xs text-muted-foreground">
            {description}
          </p>
        )}
        {error && (
          <p id={errorId} className="text-sm text-destructive">
            {error.message}
          </p>
        )}
      </div>
    );
  }
);
FormField.displayName = "FormField";

interface FormTextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: FieldError;
  description?: string;
}

const FormTextarea = React.forwardRef<HTMLTextAreaElement, FormTextareaProps>(
  ({ label, error, description, id, className, name, ...props }, ref) => {
    const reactId = React.useId();
    const fieldId = id ?? name ?? reactId;
    const errorId = `${fieldId}-error`;
    const descriptionId = `${fieldId}-description`;

    return (
      <div className="space-y-2">
        <Label htmlFor={fieldId}>{label}</Label>
        <Textarea
          ref={ref}
          id={fieldId}
          name={name}
          aria-describedby={getDescribedBy(error, errorId, description, descriptionId)}
          aria-invalid={!!error}
          className={cn(error && "border-destructive", className)}
          {...props}
        />
        {description && !error && (
          <p id={descriptionId} className="text-xs text-muted-foreground">
            {description}
          </p>
        )}
        {error && (
          <p id={errorId} className="text-sm text-destructive">
            {error.message}
          </p>
        )}
      </div>
    );
  }
);
FormTextarea.displayName = "FormTextarea";

export { FormField, FormTextarea };
