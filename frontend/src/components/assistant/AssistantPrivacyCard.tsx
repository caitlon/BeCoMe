import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { describeError } from "@/lib/errorMessages";
import { useToast } from "@/hooks/use-toast";
import "./i18n";

/**
 * The profile page's "hide my opinions from other members' assistant" card.
 * Lives in this lazy chunk (loaded only through components/assistant/index.tsx's
 * AssistantProfileSlot) rather than in Profile.tsx, so that Profile -- always
 * bundled -- carries none of its copy. The generic "Error" toast title is the
 * one string borrowed from outside the assistant namespace: "profile" is
 * always loaded and the word is not about the assistant.
 */
export function AssistantPrivacyCard() {
  const { t } = useTranslation("assistant");
  const { t: tProfile } = useTranslation("profile");
  const { t: tCommon } = useTranslation();
  const { user, setCurrentUser } = useAuth();
  const { toast } = useToast();
  const id = useId();
  const [isSaving, setIsSaving] = useState(false);

  if (!user) return null;

  const handleToggle = async (next: boolean) => {
    setIsSaving(true);
    try {
      // The response is the updated user: hand it to the context directly.
      // refreshUser() would flip the auth status to "loading", and ProtectedRoute
      // would swap the whole page for a loader, dropping focus and scroll.
      const updated = await api.updateCurrentUser({ assistant_objection: next });
      setCurrentUser(updated);
      toast({
        title: next ? t("privacy.enabledToast") : t("privacy.disabledToast"),
      });
    } catch (error) {
      toast({
        title: tProfile("toast.error"),
        description: describeError(error, tCommon, t("privacy.failed")),
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("privacy.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-start gap-2">
          <Checkbox
            id={id}
            className="mt-0.5"
            checked={user.assistant_objection}
            onCheckedChange={(checked) => handleToggle(checked === true)}
            disabled={isSaving}
            aria-describedby={`${id}-description`}
          />
          <Label htmlFor={id} className="cursor-pointer leading-snug">
            {t("privacy.label")}
          </Label>
        </div>
        <p id={`${id}-description`} className="text-sm text-muted-foreground mt-2">
          {t("privacy.description")}
        </p>
      </CardContent>
    </Card>
  );
}
