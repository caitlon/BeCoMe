import { useEffect } from "react";
import { Link } from "react-router";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { PageShell } from "@/components/layout/PageShell";
import { HeroSection } from "@/components/layout/HeroSection";
import { Button } from "@/components/ui/button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { fadeInUp } from "@/lib/motion";

/** Sections that are a heading and one paragraph, in the order they appear on the page. */
const PLAIN_SECTIONS = ["results", "assistant"] as const;
const CLOSING_SECTIONS = ["account", "warranty", "law"] as const;

// A missed lookup returns the key as a string; keep the page alive without the list.
// See the same guard in Privacy.tsx.
const asList = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const Terms = () => {
  const { t } = useTranslation("terms");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.terms"));

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const renderSection = (key: string) => (
    <motion.div key={key} {...fadeInUp}>
      <h2 className="text-section-title mb-4">{t(`${key}.heading`)}</h2>
      <p className="text-muted-foreground leading-relaxed">{t(`${key}.body`)}</p>
    </motion.div>
  );

  return (
    <PageShell variant="content" footer>
      <HeroSection title={t("meta.title")} subtitle={t("meta.subtitle")} />

      <section className="py-12 md:py-16">
        <div className="container mx-auto px-6">
          <div className="max-w-3xl mx-auto space-y-12">
            <motion.p {...fadeInUp} className="text-sm text-muted-foreground">
              {t("meta.updated")}
            </motion.p>

            <motion.div {...fadeInUp}>
              <h2 className="text-section-title mb-4">{t("operator.heading")}</h2>
              <p className="text-muted-foreground leading-relaxed">{t("operator.body")}</p>
              <p className="mt-3">
                <a
                  href={`mailto:${t("operator.email")}`}
                  className="underline underline-offset-4 hover:text-foreground"
                >
                  {t("operator.email")}
                </a>
              </p>
            </motion.div>

            {PLAIN_SECTIONS.map(renderSection)}

            <motion.div {...fadeInUp}>
              <h2 className="text-section-title mb-4">{t("rules.heading")}</h2>
              <p className="text-muted-foreground leading-relaxed">{t("rules.intro")}</p>
              <ul className="mt-4 space-y-2 list-disc pl-5">
                {asList(t("rules.items", { returnObjects: true })).map((item) => (
                  <li key={item} className="text-muted-foreground leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>

            {CLOSING_SECTIONS.map(renderSection)}

            <motion.div {...fadeInUp}>
              <h2 className="text-section-title mb-4">{t("privacy.heading")}</h2>
              <p className="text-muted-foreground leading-relaxed">{t("privacy.body")}</p>
              <Button variant="secondary" className="mt-6" asChild>
                <Link to="/privacy">{t("privacy.link")}</Link>
              </Button>
            </motion.div>
          </div>
        </div>
      </section>
    </PageShell>
  );
};

export default Terms;
