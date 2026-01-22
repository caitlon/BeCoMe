import * as React from "react";
import { Loader2 } from "lucide-react";

import { Button, ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SubmitButtonProps extends Omit<ButtonProps, "type"> {
  isLoading?: boolean;
  loadingText?: string;
}

const SubmitButton = React.forwardRef<HTMLButtonElement, SubmitButtonProps>(
  (
    { isLoading, loadingText, children, disabled, className, ...props },
    ref
  ) => {
    return (
      <Button
        ref={ref}
        type="submit"
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        className={cn(className)}
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
