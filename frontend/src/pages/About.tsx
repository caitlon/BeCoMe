import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { ArrowRight, BookOpen, FileText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

const About = () => {
  const { t } = useTranslation("about");

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      {/* Hero Section */}
      <section className="pt-24 pb-12 md:pt-32 md:pb-16 bg-secondary/30">
        <div className="container mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="max-w-3xl"
          >
            <h1 className="font-display text-3xl md:text-5xl font-normal mb-4">
              {t("hero.title")}
            </h1>
            <p className="text-lg text-muted-foreground">{t("hero.subtitle")}</p>
          </motion.div>
        </div>
      </section>

      {/* Introduction */}
      <section className="py-12 md:py-16">
        <div className="container mx-auto px-6">
          <div className="max-w-3xl">
            <motion.div {...fadeInUp}>
              <h2 className="font-display text-2xl md:text-3xl font-normal mb-6">
                {t("challenge.title")}
              </h2>
              <div className="prose prose-neutral dark:prose-invert">
                <p className="text-muted-foreground leading-relaxed mb-4">
                  {t("challenge.paragraph1")}
                </p>
                <p className="text-muted-foreground leading-relaxed">
                  {t("challenge.paragraph2")}
                </p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* The Method */}
      <section className="py-12 md:py-16 bg-card">
        <div className="container mx-auto px-6">
          <div className="max-w-3xl">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
            >
              <h2 className="font-display text-2xl md:text-3xl font-normal mb-6">
                {t("method.title")}
              </h2>
              <div className="prose prose-neutral dark:prose-invert">
                <p className="text-muted-foreground leading-relaxed mb-4">
                  {t("method.paragraph1")}
                </p>
                <p className="text-muted-foreground leading-relaxed mb-6">
                  {t("method.paragraph2")}
                </p>
              </div>
              <Button variant="outline" asChild className="gap-2">
                <Link to="/docs">
                  <FileText className="h-4 w-4" />
                  {t("method.learnMore")}
                </Link>
              </Button>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Applications */}
      <section className="py-12 md:py-16">
        <div className="container mx-auto px-6">
          <div className="max-w-3xl">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
            >
              <h2 className="font-display text-2xl md:text-3xl font-normal mb-6">
                {t("applications.title")}
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-6">
                {t("applications.subtitle")}
              </p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  "applications.items.stateSecurity",
                  "applications.items.publicHealth",
                  "applications.items.investment",
                  "applications.items.floods",
                  "applications.items.energy",
                  "applications.items.itContracts",
                  "applications.items.budget",
                  "applications.items.risk",
                ].map((key) => (
                  <li
                    key={key}
                    className="flex items-center gap-2 text-muted-foreground"
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                    {t(key)}
                  </li>
                ))}
              </ul>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Authors */}
      <section className="py-12 md:py-16 bg-card">
        <div className="container mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="font-display text-2xl md:text-3xl font-normal mb-6">
              {t("authors.title")}
            </h2>
            <Card className="max-w-xl">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-secondary flex items-center justify-center">
                    <BookOpen className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="font-medium">Prof. Ing. Ivan Vrana, DrSc.</p>
                    <p className="font-medium">Ing. Jan Tyrychtr, PhD.</p>
                    <p className="text-sm text-muted-foreground mt-2">
                      {t("authors.department")}
                      <br />
                      {t("authors.faculty")}
                      <br />
                      {t("authors.university")}
                    </p>
                  </div>
                </div>
                <div className="mt-6 pt-4 border-t">
                  <p className="text-xs text-muted-foreground">
                    <strong>{t("authors.citation")}</strong>{" "}
                    {t("authors.citationText")}
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-primary text-primary-foreground">
        <div className="container mx-auto px-6 text-center">
          <h2 className="font-display text-2xl md:text-3xl mb-4">
            {t("cta.title")}
          </h2>
          <p className="text-primary-foreground/80 mb-8 max-w-xl mx-auto">
            {t("cta.subtitle")}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button variant="secondary" size="lg" asChild>
              <Link to="/#case-studies">{t("cta.viewCaseStudies")}</Link>
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="gap-2 bg-transparent border-primary-foreground/30 text-primary-foreground hover:bg-primary-foreground/10"
              asChild
            >
              <Link to="/register">
                {t("cta.startProject")}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default About;
