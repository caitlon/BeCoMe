import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  ChevronRight,
  Users,
  Calculator,
  BarChart3,
  FileText,
  List,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

const Documentation = () => {
  const { t } = useTranslation("docs");
  const [activeSection, setActiveSection] = useState("getting-started");

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      const sections = [
        "getting-started",
        "expert-opinions",
        "results",
        "visualization",
        "glossary",
      ];

      for (const section of sections) {
        const element = document.getElementById(section);
        if (element) {
          const rect = element.getBoundingClientRect();
          if (rect.top <= 150 && rect.bottom >= 150) {
            setActiveSection(section);
            break;
          }
        }
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 100;
      const top = element.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: "smooth" });
    }
  };

  const tocItems = [
    { id: "getting-started", label: t("gettingStarted.title"), icon: BookOpen },
    { id: "expert-opinions", label: t("expertOpinions.title"), icon: Users },
    { id: "results", label: t("results.title"), icon: Calculator },
    { id: "visualization", label: t("visualization.title"), icon: BarChart3 },
    { id: "glossary", label: t("glossary.title"), icon: FileText },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      {/* Hero Section */}
      <section className="pt-24 pb-8 md:pt-32 md:pb-12 bg-secondary/30">
        <div className="container mx-auto px-6">
          <motion.div {...fadeInUp} className="max-w-3xl">
            <h1 className="font-display text-3xl md:text-5xl font-normal mb-4">
              {t("title")}
            </h1>
            <p className="text-lg text-muted-foreground">{t("subtitle")}</p>
          </motion.div>
        </div>
      </section>

      {/* Main Content */}
      <section className="flex-1 py-8 md:py-12">
        <div className="container mx-auto px-6">
          <div className="flex flex-col lg:flex-row gap-8">
            {/* Sidebar TOC */}
            <aside className="lg:w-64 shrink-0">
              <div className="lg:sticky lg:top-24">
                <div className="flex items-center gap-2 mb-4 text-sm font-medium">
                  <List className="h-4 w-4" />
                  {t("tableOfContents")}
                </div>
                <nav className="space-y-1">
                  {tocItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => scrollToSection(item.id)}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors text-left ${
                        activeSection === item.id
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted"
                      }`}
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      {item.label}
                    </button>
                  ))}
                </nav>
              </div>
            </aside>

            {/* Content */}
            <main className="flex-1 max-w-3xl">
              {/* Getting Started */}
              <section id="getting-started" className="mb-12">
                <h2 className="font-display text-2xl md:text-3xl font-normal mb-4">
                  {t("gettingStarted.title")}
                </h2>
                <p className="text-muted-foreground mb-6">
                  {t("gettingStarted.intro")}
                </p>

                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">
                        {t("gettingStarted.createProject.title")}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ol className="space-y-2">
                        {[1, 2, 3, 4].map((step) => (
                          <li
                            key={step}
                            className="flex items-start gap-3 text-muted-foreground"
                          >
                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
                              {step}
                            </span>
                            {t(`gettingStarted.createProject.step${step}`)}
                          </li>
                        ))}
                      </ol>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">
                        {t("gettingStarted.inviteExperts.title")}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-4">
                        {t("gettingStarted.inviteExperts.description")}
                      </p>
                      <ol className="space-y-2">
                        {[1, 2, 3, 4].map((step) => (
                          <li
                            key={step}
                            className="flex items-start gap-3 text-muted-foreground"
                          >
                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
                              {step}
                            </span>
                            {t(`gettingStarted.inviteExperts.step${step}`)}
                          </li>
                        ))}
                      </ol>
                    </CardContent>
                  </Card>
                </div>
              </section>

              {/* Expert Opinions */}
              <section id="expert-opinions" className="mb-12">
                <h2 className="font-display text-2xl md:text-3xl font-normal mb-4">
                  {t("expertOpinions.title")}
                </h2>
                <p className="text-muted-foreground mb-6">
                  {t("expertOpinions.intro")}
                </p>

                <div className="space-y-6">
                  {/* Crisp */}
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <Calculator className="h-5 w-5 text-primary" />
                        </div>
                        <CardTitle className="text-lg">
                          {t("expertOpinions.crisp.title")}
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-muted-foreground">
                        {t("expertOpinions.crisp.description")}
                      </p>
                      <p className="text-sm font-mono bg-muted px-3 py-2 rounded">
                        {t("expertOpinions.crisp.example")}
                      </p>
                    </CardContent>
                  </Card>

                  {/* Fuzzy */}
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <BarChart3 className="h-5 w-5 text-primary" />
                        </div>
                        <CardTitle className="text-lg">
                          {t("expertOpinions.fuzzy.title")}
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <p className="text-muted-foreground">
                        {t("expertOpinions.fuzzy.description")}
                      </p>
                      <ul className="space-y-2">
                        <li className="flex items-start gap-2 text-muted-foreground">
                          <ChevronRight className="h-5 w-5 shrink-0 text-primary" />
                          <span>
                            <strong>{t("expertOpinions.fuzzy.lowerLabel")}</strong>{" "}
                            {t("expertOpinions.fuzzy.lower")}
                          </span>
                        </li>
                        <li className="flex items-start gap-2 text-muted-foreground">
                          <ChevronRight className="h-5 w-5 shrink-0 text-primary" />
                          <span>
                            <strong>{t("expertOpinions.fuzzy.peakLabel")}</strong>{" "}
                            {t("expertOpinions.fuzzy.peak")}
                          </span>
                        </li>
                        <li className="flex items-start gap-2 text-muted-foreground">
                          <ChevronRight className="h-5 w-5 shrink-0 text-primary" />
                          <span>
                            <strong>{t("expertOpinions.fuzzy.upperLabel")}</strong>{" "}
                            {t("expertOpinions.fuzzy.upper")}
                          </span>
                        </li>
                      </ul>
                      <p className="text-sm font-mono bg-muted px-3 py-2 rounded">
                        {t("expertOpinions.fuzzy.example")}
                      </p>
                      <p className="text-sm text-muted-foreground italic">
                        {t("expertOpinions.fuzzy.rule")}
                      </p>
                    </CardContent>
                  </Card>

                  {/* Likert */}
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <Users className="h-5 w-5 text-primary" />
                        </div>
                        <CardTitle className="text-lg">
                          {t("expertOpinions.likert.title")}
                        </CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <p className="text-muted-foreground">
                        {t("expertOpinions.likert.description")}
                      </p>
                      <ul className="space-y-1 text-sm">
                        {[
                          "stronglyDisagree",
                          "ratherDisagree",
                          "neutral",
                          "ratherAgree",
                          "stronglyAgree",
                        ].map((key) => (
                          <li
                            key={key}
                            className="font-mono text-muted-foreground"
                          >
                            {t(`expertOpinions.likert.scale.${key}`)}
                          </li>
                        ))}
                      </ul>
                      <p className="text-sm font-mono bg-muted px-3 py-2 rounded">
                        {t("expertOpinions.likert.example")}
                      </p>
                    </CardContent>
                  </Card>
                </div>
              </section>

              {/* Results */}
              <section id="results" className="mb-12">
                <h2 className="font-display text-2xl md:text-3xl font-normal mb-4">
                  {t("results.title")}
                </h2>
                <p className="text-muted-foreground mb-6">{t("results.intro")}</p>

                <div className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">
                        {t("results.bestCompromise.title")}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <p className="text-muted-foreground">
                        {t("results.bestCompromise.description")}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {t("results.bestCompromise.centroid")}
                      </p>
                    </CardContent>
                  </Card>

                  <div className="grid md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">
                          {t("results.arithmeticMean.title")}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-muted-foreground">
                          {t("results.arithmeticMean.description")}
                        </p>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">
                          {t("results.median.title")}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-muted-foreground">
                          {t("results.median.description")}
                        </p>
                      </CardContent>
                    </Card>
                  </div>

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">
                        {t("results.maxError.title")}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <p className="text-muted-foreground">
                        {t("results.maxError.description")}
                      </p>
                      <p className="text-sm text-muted-foreground italic">
                        {t("results.maxError.interpretation")}
                      </p>
                    </CardContent>
                  </Card>
                </div>
              </section>

              {/* Visualization */}
              <section id="visualization" className="mb-12">
                <h2 className="font-display text-2xl md:text-3xl font-normal mb-4">
                  {t("visualization.title")}
                </h2>
                <p className="text-muted-foreground mb-6">
                  {t("visualization.description")}
                </p>

                <Card>
                  <CardContent className="pt-6">
                    <ul className="space-y-3">
                      {[
                        { key: "xAxis", color: null },
                        { key: "yAxis", color: null },
                        { key: "gray", color: "bg-muted-foreground/30" },
                        { key: "blue", color: "bg-blue-500" },
                        { key: "green", color: "bg-green-500" },
                        { key: "black", color: "bg-foreground" },
                      ].map((item) => (
                        <li
                          key={item.key}
                          className="flex items-center gap-3 text-muted-foreground"
                        >
                          {item.color && (
                            <div className={`w-6 h-0.5 ${item.color}`} />
                          )}
                          {!item.color && <div className="w-6" />}
                          {t(`visualization.elements.${item.key}`)}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-4 text-sm text-muted-foreground italic">
                      {t("visualization.tip")}
                    </p>
                  </CardContent>
                </Card>
              </section>

              {/* Glossary */}
              <section id="glossary" className="mb-12">
                <h2 className="font-display text-2xl md:text-3xl font-normal mb-4">
                  {t("glossary.title")}
                </h2>

                <div className="space-y-4">
                  {["fuzzyNumber", "centroid", "membership", "aggregation"].map(
                    (term) => (
                      <Card key={term}>
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base font-medium">
                            {t(`glossary.${term}.term`)}
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <p className="text-sm text-muted-foreground">
                            {t(`glossary.${term}.definition`)}
                          </p>
                        </CardContent>
                      </Card>
                    )
                  )}
                </div>
              </section>
            </main>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Documentation;
