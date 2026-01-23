import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { UserPlus, Mail, Send } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

export function StepInviteExperts() {
  const { t } = useTranslation("onboarding");

  return (
    <div className="flex flex-col items-center px-6 py-8">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", duration: 0.6 }}
        className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6"
      >
        <UserPlus className="h-8 w-8 text-primary" />
      </motion.div>

      <motion.h2
        {...fadeInUp}
        className="font-display text-2xl md:text-3xl font-normal mb-2 text-center"
      >
        {t("steps.inviteExperts.title")}
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5 }}
        className="text-muted-foreground text-center max-w-md mb-8"
      >
        {t("steps.inviteExperts.description")}
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="w-full max-w-md"
      >
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div>
              <Label htmlFor="invite-email">
                {t("steps.inviteExperts.form.email")}
              </Label>
              <div className="flex gap-2 mt-1">
                <div className="relative flex-1">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="invite-email"
                    placeholder={t("steps.inviteExperts.form.emailPlaceholder")}
                    className="pl-10"
                    readOnly
                    aria-readonly="true"
                  />
                </div>
                <Button
                  type="button"
                  size="icon"
                  className="shrink-0"
                  aria-label={t("steps.inviteExperts.form.invite")}
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
              className="flex items-center gap-3 p-3 bg-muted rounded-lg"
            >
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                <span className="text-xs font-medium">
                  {t("steps.inviteExperts.samples.0.initials")}
                </span>
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">
                  {t("steps.inviteExperts.samples.0.name")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("steps.inviteExperts.samples.0.email")}
                </p>
              </div>
              <span className="text-xs text-primary">
                {t("steps.inviteExperts.samples.0.status")}
              </span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5, duration: 0.5 }}
              className="flex items-center gap-3 p-3 bg-muted rounded-lg"
            >
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                <span className="text-xs font-medium">
                  {t("steps.inviteExperts.samples.1.initials")}
                </span>
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">
                  {t("steps.inviteExperts.samples.1.name")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("steps.inviteExperts.samples.1.email")}
                </p>
              </div>
              <span className="text-xs text-green-600">
                {t("steps.inviteExperts.samples.1.status")}
              </span>
            </motion.div>

            <p className="text-xs text-muted-foreground italic">
              {t("steps.inviteExperts.hint")}
            </p>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
