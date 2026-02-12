import { useEffect } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { CaseStudyCard } from "@/components/CaseStudyCard";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useLocalizedCaseStudies } from "@/hooks/useLocalizedCaseStudies";

const CaseStudies = () => {
  const { t } = useTranslation("caseStudies");
  const { t: tCommon } = useTranslation();
  useDocumentTitle(tCommon("pageTitle.caseStudies"));
  const studies = useLocalizedCaseStudies();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main id="main-content">
        {/* Hero Section */}
        <section className="pt-24 pb-12 md:pt-32 md:pb-16 bg-secondary/30">
          <div className="container mx-auto px-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="max-w-3xl mx-auto"
            >
              <h1 className="font-display text-3xl md:text-5xl font-normal mb-4">
                {t("listing.title")}
              </h1>
              <p className="text-lg text-muted-foreground">
                {t("listing.subtitle")}
              </p>
            </motion.div>
          </div>
        </section>

        {/* Case Study Cards */}
        <section className="py-12 md:py-16">
          <div className="container mx-auto px-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
              {studies.map((study, index) => (
                <motion.div
                  key={study.id}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  whileHover={{ y: -4 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.1, duration: 0.5 }}
                >
                  <CaseStudyCard study={study} showScale />
                </motion.div>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
};

export default CaseStudies;
