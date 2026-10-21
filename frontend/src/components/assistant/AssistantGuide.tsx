import type { ReactNode } from "react";
import { Link } from "react-router";
import { Trans, useTranslation } from "react-i18next";
import { ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import "./i18n";

/**
 * The assistant's part of the documentation page. Lives in this lazy chunk
 * (loaded only through components/assistant/index.tsx's useAssistantGuide)
 * rather than in Documentation.tsx, so that the page -- always bundled --
 * carries none of its copy, not even the assistant.json key names.
 */

const transComponents = {
  b: <strong />,
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
