import type { ReactNode } from "react";
import { Link } from "react-router";
import { motion } from "framer-motion";
import { Trans, useTranslation } from "react-i18next";
import { ChevronRight, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fadeInUp } from "@/lib/motion";
import "./i18n";

/**
 * The assistant's part of the documentation page and of the onboarding tour.
 * Lives in this lazy chunk (loaded only through components/assistant/index.tsx's
 * useAssistantGuide) rather than in Documentation.tsx and Onboarding.tsx, so
 * that those pages -- always bundled -- carry none of its copy, not even the
 * assistant.json key names.
 */

const transComponents = {
  b: <strong />,
  icon: <Sparkles className="inline h-4 w-4 align-text-bottom text-primary" aria-hidden="true" />,
  privacy: <Link to="/privacy" className="underline underline-offset-4 hover:text-foreground" />,
};

function GuideCard({ titleKey, children }: { readonly titleKey: string; readonly children: ReactNode }) {
  const { t } = useTranslation("assistant");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t(titleKey)}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function GuideList({ keys }: { readonly keys: readonly string[] }) {
  const { t } = useTranslation("assistant");

  return (
    <ul className="space-y-2">
      {keys.map((key) => (
        <li key={key} className="flex items-start gap-2 text-muted-foreground">
          <ChevronRight className="h-5 w-5 shrink-0 text-primary" />
          <span>
            <Trans t={t} i18nKey={key} components={transComponents} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The label of the table-of-contents entry, as a node for SidebarNav. */
export function AssistantDocsNavLabel() {
  const { t } = useTranslation("assistant");

  return <>{t("guide.docs.title")}</>;
}

/** The `#assistant` section of the documentation page. */
export function AssistantDocsSection() {
  const { t } = useTranslation("assistant");

  return (
    <section id="assistant" className="mb-12">
      <h2 className="text-section-title mb-4">{t("guide.docs.title")}</h2>
      <p className="text-muted-foreground mb-6">{t("guide.docs.intro")}</p>

      <div className="space-y-6">
        <GuideCard titleKey="guide.docs.where.title">
          <p className="text-muted-foreground">
            <Trans t={t} i18nKey="guide.docs.where.body" components={transComponents} />
          </p>
        </GuideCard>

        <GuideCard titleKey="guide.docs.answers.title">
          <GuideList
            keys={[
              "guide.docs.answers.method",
              "guide.docs.answers.project",
              "guide.docs.answers.app",
              "guide.docs.answers.readOnly",
            ]}
          />
        </GuideCard>

        <GuideCard titleKey="guide.docs.limits.title">
          <GuideList
            keys={[
              "guide.docs.limits.rate",
              "guide.docs.limits.time",
              "guide.docs.limits.storage",
              "guide.docs.limits.history",
            ]}
          />
        </GuideCard>

        <GuideCard titleKey="guide.docs.data.title">
          <GuideList
            keys={["guide.docs.data.sent", "guide.docs.data.sensitive", "guide.docs.data.objection"]}
          />
        </GuideCard>
      </div>
    </section>
  );
}

const tourHintComponents = {
  docs: (
    <Link
      to="/docs"
      target="_blank"
      rel="noopener noreferrer"
      className="underline underline-offset-4 hover:text-foreground"
    />
  ),
  sr: <span className="sr-only" />,
};

/** The tour step that introduces the assistant. Laid out like the steps in components/onboarding. */
export function AssistantTourStep() {
  const { t } = useTranslation("assistant");

  return (
    <div className="flex flex-col items-center px-6 py-8">
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", duration: 0.6 }}
        className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6"
      >
        <Sparkles className="h-8 w-8 text-primary" aria-hidden="true" />
      </motion.div>

      <motion.h2 {...fadeInUp} className="text-section-title mb-2 text-center">
        {t("guide.tour.title")}
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5 }}
        className="text-muted-foreground text-center max-w-md mb-8"
      >
        <Trans t={t} i18nKey="guide.tour.body" components={transComponents} />
      </motion.p>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="text-xs text-muted-foreground italic text-center"
      >
        <Trans t={t} i18nKey="guide.tour.hint" components={tourHintComponents} />
      </motion.p>
    </div>
  );
}
