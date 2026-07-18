import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
  const navigate = useNavigate();
  const { toast } = useToast();
  const { t: tCommon } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);

  const execute = async (action: () => Promise<void>) => {
    setIsLoading(true);
    try {
      await action();
      toast({
        title: messages.successTitle,
        description: messages.successDescription,
      });
      navigate("/projects");
    } catch (error) {
      toast({
        title: messages.errorTitle,
        description: describeError(error, tCommon, messages.errorFallback),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return { isLoading, execute };
}
