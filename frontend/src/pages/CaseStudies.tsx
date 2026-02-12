import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
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
                  <Link to={`/case-study/${study.id}`}>
                    <Card className="h-full group hover:shadow-lg hover:border-primary/30 transition-all duration-300 cursor-pointer">
                      <CardContent className="pt-6 pb-6">
                        <div className="flex items-start gap-4">
                          <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                            <study.icon className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" aria-hidden="true" />
                          </div>
                          <div>
                            <h3 className="font-display font-medium text-lg mb-1 group-hover:text-primary transition-colors">
                              {study.title}
                            </h3>
                            <p className="text-sm text-muted-foreground mb-3">
                              {study.description}
                            </p>
                            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <Users className="h-3 w-3" aria-hidden="true" />
                                <span className="font-mono">
                                  {study.experts} {t("common.experts")}
                                </span>
                              </span>
                              <span className="font-mono bg-muted px-2 py-0.5 rounded">
                                {study.scaleMin}–{study.scaleMax} {study.scaleUnit}
                              </span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
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
