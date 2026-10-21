import type { ReactElement } from "react";
import { Link } from "react-router";
import { Trans, useTranslation } from "react-i18next";
import { ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import "./i18n";

/**
 * The assistant's part of the documentation page. Lives in this lazy chunk
 * (loaded only through components/assistant/index.tsx's slots) rather than in
 * Documentation.tsx, so that the page -- always bundled -- carries none of
 * its copy, not even the assistant.json key names.
 */

const bold = { b: <strong /> };
const privacyLink = <Link to="/privacy" className="underline underline-offset-4 hover:text-foreground" />;

interface GuideItem {
  readonly key: string;
  readonly components?: Record<string, ReactElement>;
}

const plain = (...keys: string[]): GuideItem[] => keys.map((key) => ({ key }));

function GuideList({ items }: { readonly items: readonly GuideItem[] }) {
  const { t } = useTranslation("assistant");

  return (
    <ul className="space-y-2">
      {items.map(({ key, components }) => (
        <li key={key} className="flex items-start gap-2 text-muted-foreground">
          <ChevronRight className="h-5 w-5 shrink-0 text-primary" />
          <span>
            <Trans t={t} i18nKey={key} components={components ?? bold} />
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
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("guide.docs.where.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              <Trans t={t} i18nKey="guide.docs.where.body" components={bold} />
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("guide.docs.answers.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <GuideList
              items={plain(
                "guide.docs.answers.method",
                "guide.docs.answers.project",
                "guide.docs.answers.app",
                "guide.docs.answers.readOnly",
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("guide.docs.limits.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <GuideList
              items={plain(
                "guide.docs.limits.rate",
                "guide.docs.limits.time",
                "guide.docs.limits.storage",
                "guide.docs.limits.history",
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("guide.docs.data.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <GuideList
              items={[
                { key: "guide.docs.data.sent", components: { privacy: privacyLink } },
                ...plain("guide.docs.data.sensitive", "guide.docs.data.objection"),
              ]}
            />
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
