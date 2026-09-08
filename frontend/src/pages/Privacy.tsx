import { useEffect } from "react";
import { Link } from "react-router";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { PageShell } from "@/components/layout/PageShell";
import { HeroSection } from "@/components/layout/HeroSection";
import { Button } from "@/components/ui/button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { fadeInUp } from "@/lib/motion";

/**
 * The sections built from a lead paragraph, a list, and a closing paragraph. Keeping them
 * in one array stops the markup repeating itself four times, and it means a translator
 * adding a bullet touches only the locale file. Every one of them carries all three parts.
 * An earlier version made the closing paragraph optional by comparing a translation against
 * its own key. That worked, but it rested on undocumented i18next behaviour: the key comes
 * back only while `parseMissingKeyHandler` is unset and `appendNamespaceToMissingKey` is
 * false, neither of which the call site can see. `i18n.exists()` is the documented way to
 * ask. Requiring all three parts avoids the question.
 */
const LIST_SECTIONS = ["collected", "cookies", "processors", "retention"] as const;

/**
 * i18next returns the key itself when a lookup misses, so `returnObjects` hands back a string
 * rather than an array and `.map` throws, taking the whole notice down to the ErrorBoundary.
 * `fallbackLng: "en"` hides a one-sided omission, so only a symmetric deletion reaches this,
 * and the locale tests would fail first. This is the second line of defence: a legal page that
 * loses one list is worse than the page it was, and far better than a page nobody can read,
 * because the controller's address and the rights section survive.
 */
const asList = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const Privacy = () => {
  const { t } = useTranslation("privacy");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.privacy"));

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

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
              <h2 className="text-section-title mb-4">{t("controller.heading")}</h2>
              <p className="text-muted-foreground leading-relaxed">
                {t("controller.body")}
              </p>
              <p className="mt-3">
                <a
                  href={`mailto:${t("controller.email")}`}
                  className="underline underline-offset-4 hover:text-foreground"
                >
                  {t("controller.email")}
                </a>
              </p>
            </motion.div>

            {LIST_SECTIONS.map((key) => (
              <motion.div key={key} {...fadeInUp}>
                <h2 className="text-section-title mb-4">{t(`${key}.heading`)}</h2>
                <p className="text-muted-foreground leading-relaxed">
                  {t(`${key}.intro`)}
                </p>
                <ul className="mt-4 space-y-2 list-disc pl-5">
                  {asList(t(`${key}.items`, { returnObjects: true })).map((item) => (
                    <li key={item} className="text-muted-foreground leading-relaxed">
                      {item}
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-muted-foreground leading-relaxed">
                  {t(`${key}.outro`)}
                </p>
              </motion.div>
            ))}

            <motion.div {...fadeInUp}>
              <h2 className="text-section-title mb-4">{t("basis.heading")}</h2>
              <p className="text-muted-foreground leading-relaxed">{t("basis.body")}</p>
            </motion.div>

            <motion.div {...fadeInUp}>
              <h2 className="text-section-title mb-4">{t("rights.heading")}</h2>
              <p className="text-muted-foreground leading-relaxed">{t("rights.intro")}</p>
              <ul className="mt-4 space-y-2 list-disc pl-5">
                {asList(t("rights.items", { returnObjects: true })).map((item) => (
                  <li key={item} className="text-muted-foreground leading-relaxed">
                    {item}
                  </li>
                ))}
              </ul>
              <Button variant="secondary" className="mt-6" asChild>
                <Link to="/profile">{t("rights.profileLink")}</Link>
              </Button>
            </motion.div>

            <motion.div {...fadeInUp}>
              <h2 className="text-section-title mb-4">{t("complaint.heading")}</h2>
              <p className="text-muted-foreground leading-relaxed">
                {t("complaint.body")}
              </p>
            </motion.div>
          </div>
        </div>
      </section>
    </PageShell>
  );
};

export default Privacy;
