import { useEffect } from "react";
import { Link } from "react-router";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  Calculator,
  BarChart3,
  Laptop,
  Wrench,
  ExternalLink,
  type LucideIcon,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { HeroSection } from "@/components/layout/HeroSection";
import { PageShell } from "@/components/layout/PageShell";
import { SidebarNav, type SidebarNavItem } from "@/components/layout/SidebarNav";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useScrollSpy } from "@/hooks/useScrollSpy";

const categories = [
  { id: "method", icon: BookOpen, labelKey: "categories.method" },
  { id: "fuzzyNumbers", icon: Calculator, labelKey: "categories.fuzzyNumbers" },
  { id: "results", icon: BarChart3, labelKey: "categories.results" },
  { id: "application", icon: Laptop, labelKey: "categories.application" },
  { id: "troubleshooting", icon: Wrench, labelKey: "categories.troubleshooting" },
] as const satisfies ReadonlyArray<{ id: string; icon: LucideIcon; labelKey: string }>;

type CategoryId = (typeof categories)[number]["id"];

const categoryIds = categories.map((c) => c.id);

const faqItems: Record<CategoryId, string[]> = {
  method: ["whatIsBecome", "whyBetterThanMean", "whenToUse"],
  fuzzyNumbers: ["whatIsFuzzy", "whatIsCentroid"],
  results: ["whatIsMaxError", "whyDifferentMedian"],
  application: ["howToCreateProject", "howToInviteExperts", "whatInputFormats"],
  troubleshooting: ["cantSeeInvitation", "noResults", "howToEditOpinion"],
};

const FAQ = () => {
  const { t } = useTranslation("faq");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.faq"));

  const { activeId, scrollToSection } = useScrollSpy(categoryIds, "method");

  useEffect(() => {
    globalThis.scrollTo(0, 0);
  }, []);

  const sidebarItems: SidebarNavItem[] = categories.map((cat) => ({
    id: cat.id,
    label: t(cat.labelKey),
    icon: cat.icon,
  }));

  return (
    <PageShell variant="content" footer mainClassName="flex-1 flex flex-col">
      <HeroSection title={t("title")} subtitle={t("subtitle")} align="left" spacing="compact" />

      {/* Main Content */}
      <section className="flex-1 py-8 md:py-12">
        <div className="container mx-auto px-6">
          <div className="flex flex-col lg:flex-row gap-8">
            <SidebarNav
              title={t("categories.title")}
              items={sidebarItems}
              activeId={activeId}
              onNavigate={scrollToSection}
            />

            {/* FAQ Content */}
            <div className="flex-1 max-w-3xl">
              {categories.map((cat) => (
                <motion.section
                  key={cat.id}
                  id={cat.id}
                  className="mb-12"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5 }}
                >
                  <h2 className="text-section-title mb-4 flex items-center gap-3">
                    <cat.icon className="h-6 w-6 text-primary" />
                    {t(cat.labelKey)}
                  </h2>
                  <p className="text-muted-foreground mb-6">
                    {t(`${cat.id}.intro`)}
                  </p>
                  <Card>
                    <CardContent className="pt-6">
                      <Accordion type="single" collapsible className="w-full border-t">
                        {faqItems[cat.id].map((itemKey) => (
                          <AccordionItem key={itemKey} value={itemKey}>
                            <AccordionTrigger className="text-left">
                              {t(`${cat.id}.${itemKey}.question`)}
                            </AccordionTrigger>
                            <AccordionContent className="text-muted-foreground">
                              {t(`${cat.id}.${itemKey}.answer`)}
                            </AccordionContent>
                          </AccordionItem>
                        ))}
                      </Accordion>
                    </CardContent>
                  </Card>
                </motion.section>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-primary text-primary-foreground">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-section-title mb-4">
            {t("cta.title")}
          </h2>
          <p className="text-primary-foreground/80 mb-8 max-w-xl mx-auto">
            {t("cta.subtitle")}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button variant="secondary" size="lg" asChild>
              <Link to="/docs">{t("cta.viewDocs")}</Link>
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="gap-2 bg-transparent border-primary-foreground/30 text-primary-foreground hover:bg-primary-foreground/10"
              asChild
            >
              <a
                href="https://github.com/caitlon/BeCoMe/issues/new"
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="h-4 w-4" />
                {t("cta.openIssue")}
              </a>
            </Button>
          </div>
        </div>
      </section>
    </PageShell>
  );
};

export default FAQ;
