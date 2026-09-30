import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button, ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SubmitButtonProps extends ButtonProps {
  isLoading?: boolean;
  loadingText?: string;
}

const SubmitButton = React.forwardRef<HTMLButtonElement, SubmitButtonProps>(
  (
    { isLoading, loadingText, children, disabled, className, type = "submit", onClick, ...props },
    ref
  ) => {
    // A disabled button cannot hold focus, so a keyboard user who pressed Enter on it would
    // fall back to <body> mid-request. While loading the button stays focusable and is marked
    // aria-disabled instead; the click handler swallows activation (a click, Enter or Space,
    // and a form's implicit submission all arrive as a click) so nothing is sent twice.
    return (
      <Button
        ref={ref}
        type={type}
        disabled={disabled}
        aria-busy={isLoading}
        aria-disabled={isLoading || undefined}
        className={cn("aria-disabled:pointer-events-none aria-disabled:opacity-50", className)}
        onClick={(event) => {
          if (isLoading) {
            event.preventDefault();
            return;
          }
          onClick?.(event);
        }}
        {...props}
      >
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            {loadingText || children}
          </>
        ) : (
          children
        )}
      </Button>
    );
  }
);
SubmitButton.displayName = "SubmitButton";

export { SubmitButton };
