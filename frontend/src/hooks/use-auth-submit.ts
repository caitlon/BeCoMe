import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useToast } from "@/hooks/use-toast";
import { describeError } from "@/lib/errorMessages";

interface AuthSubmitMessages {
  successTitle: string;
  successDescription: string;
  errorTitle: string;
  errorFallback: string;
}

export function useAuthSubmit(messages: AuthSubmitMessages) {
  const { toast } = useToast();
  const { t: tCommon } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);
  const submittingRef = useRef(false);

  const execute = async (
    action: () => Promise<void>,
    onError?: (error: unknown) => boolean
  ) => {
    if (submittingRef.current) return; // ignore re-entrant submits (double-click)
    submittingRef.current = true;
    setIsLoading(true);
    try {
      await action();
      toast({
        title: messages.successTitle,
        description: messages.successDescription,
      });
      // No redirect here: login() flips the session to authenticated, and
      // GuestRoute then replaces /login with the page the visitor came from (or
      // /projects), so Back never reopens the form.
    } catch (error) {
      // onError lets a caller claim an error it already rendered its own state
      // for (e.g. an unverified-account 403), so the generic toast below does
      // not pile a redundant message on top of it.
      const handled = onError?.(error) ?? false;
      if (!handled) {
        toast({
          title: messages.errorTitle,
          description: describeError(error, tCommon, messages.errorFallback),
          variant: "destructive",
        });
      }
    } finally {
      setIsLoading(false);
      submittingRef.current = false;
    }
  };

  return { isLoading, execute };
}
