import * as React from "react";
import { useState } from "react";
import { FieldError } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface PasswordInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  error?: FieldError;
}

const PasswordInput = React.forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ label, error, id, className, ...props }, ref) => {
    const [showPassword, setShowPassword] = useState(false);

    const fieldId = id || label.toLowerCase().replace(/\s+/g, "-");
    const errorId = `${fieldId}-error`;

    return (
      <div className="space-y-2">
        <Label htmlFor={fieldId}>{label}</Label>
        <div className="relative">
          <Input
            ref={ref}
            id={fieldId}
            type={showPassword ? "text" : "password"}
            aria-describedby={error ? errorId : undefined}
            aria-invalid={!!error}
            className={cn("pr-10", error && "border-destructive", className)}
            {...props}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
        </div>
        {error && (
          <p id={errorId} className="text-sm text-destructive">
            {error.message}
          </p>
        )}
      </div>
    );
  }
);
PasswordInput.displayName = "PasswordInput";

export { PasswordInput };
