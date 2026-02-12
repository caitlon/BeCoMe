import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { FuzzyTriangleSVG } from "@/components/visualizations/FuzzyTriangleSVG";
import { CaseStudyCard } from "@/components/CaseStudyCard";
import { ArrowRight, Users, Calculator, Target } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useLocalizedCaseStudies } from "@/hooks/useLocalizedCaseStudies";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 }
};

const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.1
    }
  }
};

const Landing = () => {
  const { t } = useTranslation("landing");
  const { t: tCommon } = useTranslation();
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  useDocumentTitle(tCommon("pageTitle.landing"));
  const localizedStudies = useLocalizedCaseStudies();

  useEffect(() => {
    if (location.hash) {
      const id = location.hash.slice(1);
      const element = document.getElementById(id);
      if (element) {
        const timeoutId = setTimeout(() => {
          element.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 100);
        return () => clearTimeout(timeoutId);
      }
    }
  }, [location.hash]);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main id="main-content">
      
      {/* Hero Section */}
      <section className="pt-32 pb-20 md:pt-40 md:pb-32 bg-gradient-to-b from-background via-background to-muted/20">
        <div className="container mx-auto px-6">
          <motion.div 
            className="max-w-4xl mx-auto text-center"
            initial="initial"
            animate="animate"
            variants={stagger}
          >
            <motion.h1
              className="font-display text-4xl md:text-6xl lg:text-7xl font-light tracking-tight mb-6"
              variants={fadeInUp}
            >
              {t("hero.title1")}
              <br />
              <span className="font-medium">{t("hero.title2")}</span>
            </motion.h1>

            <motion.p
              className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10"
              variants={fadeInUp}
            >
              {t("hero.subtitle")}
            </motion.p>

            <motion.div variants={fadeInUp}>
              <Button size="lg" className="group gap-2 shadow-md hover:shadow-xl hover:scale-[1.03] transition-all duration-300" asChild>
                <Link to={isAuthenticated ? "/projects" : "/register"}>
                  {isAuthenticated ? t("hero.goToProjects") : t("hero.startProject")}
                  <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
                </Link>
              </Button>
            </motion.div>
          </motion.div>
          
          {/* Animated Triangle Visualization */}
          <motion.div 
            className="mt-16 md:mt-24"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.6 }}
          >
            <FuzzyTriangleSVG />
          </motion.div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 md:py-32 bg-card">
        <div className="container mx-auto px-6">
          <motion.div
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="font-display text-3xl md:text-4xl font-normal mb-4">
              {t("howItWorks.title")}
            </h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              {t("howItWorks.subtitle")}
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                icon: Users,
                titleKey: "howItWorks.collect.title",
                descriptionKey: "howItWorks.collect.description",
              },
              {
                icon: Calculator,
                titleKey: "howItWorks.calculate.title",
                descriptionKey: "howItWorks.calculate.description",
              },
              {
                icon: Target,
                titleKey: "howItWorks.consensus.title",
                descriptionKey: "howItWorks.consensus.description",
              },
            ].map((step, index) => (
              <motion.div
                key={step.titleKey}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
              >
                <Card className="h-full border-border/50">
                  <CardContent className="pt-8 pb-8 text-center">
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
                      <step.icon className="h-6 w-6" />
                    </div>
                    <h3 className="font-display text-xl font-medium mb-3">
                      {t(step.titleKey)}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {t(step.descriptionKey)}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          <motion.div
            className="text-center mt-10"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.5 }}
          >
            <Link
              to="/about"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("howItWorks.learnMore")}
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Case Studies */}
      <section id="case-studies" className="py-20 md:py-32">
        <div className="container mx-auto px-6">
          <motion.div
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="font-display text-3xl md:text-4xl font-normal mb-4">
              {t("caseStudies.title")}
            </h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              {t("caseStudies.subtitle")}
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {localizedStudies.map((study, index) => (
              <motion.div
                key={study.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                whileHover={{ y: -4 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
              >
                <CaseStudyCard study={study} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative py-16 md:py-24 bg-primary text-primary-foreground overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/3 h-px bg-gradient-to-r from-transparent via-primary-foreground/20 to-transparent" aria-hidden="true" />
        <div className="absolute top-10 left-10 w-32 h-32 rounded-full bg-primary-foreground/5 blur-2xl" aria-hidden="true" />
        <div className="absolute bottom-10 right-10 w-40 h-40 rounded-full bg-primary-foreground/5 blur-2xl" aria-hidden="true" />
        <div className="container mx-auto px-6">
          <motion.div
            className="max-w-2xl mx-auto text-center"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="font-display text-3xl md:text-4xl font-normal mb-6">
              {t("cta.title")}
            </h2>
            <p className="text-primary-foreground/80 mb-8">{t("cta.subtitle")}</p>
            <Button variant="secondary" size="lg" className="group gap-2 shadow-md hover:shadow-xl hover:scale-[1.03] transition-all duration-300" asChild>
              <Link to={isAuthenticated ? "/projects" : "/register"}>
                {t("cta.button")}
                <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
            </Button>
          </motion.div>
        </div>
      </section>

      </main>
      <Footer />
    </div>
  );
};

export default Landing;
