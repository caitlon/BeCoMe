import { useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  ArrowLeft,
  Users,
  Target,
  BarChart3,
  Info,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import {
  useLocalizedCaseStudyById,
  useLocalizedLikertLabel,
} from "@/hooks/useLocalizedCaseStudies";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const CaseStudy = () => {
  const { t } = useTranslation("caseStudies");
  const { t: tCommon } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const caseStudy = useLocalizedCaseStudyById(id || "");
  useDocumentTitle(tCommon("pageTitle.caseStudy"));

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [id]);

  if (!caseStudy) {
    return (
      <div className="min-h-screen bg-background">
        <Navbar />
        <div className="container mx-auto px-6 py-20 text-center">
          <h1 className="font-display text-3xl md:text-4xl font-light mb-4">
            {tCommon("notFound.title")}
          </h1>
          <Button variant="outline" asChild>
            <Link to="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              {tCommon("notFound.backHome")}
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const IconComponent = caseStudy.icon;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Navbar />
      <main id="main-content">
      {/* Hero Section */}
      <section className="pt-24 pb-12 md:pt-32 md:pb-16 bg-secondary/30">
        <div className="container mx-auto px-6">
          <Link
            to="/case-studies"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("listing.title")}
          </Link>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-xl bg-background flex items-center justify-center shadow-sm">
                <IconComponent className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Users className="h-4 w-4" aria-hidden="true" />
                <span className="font-mono">
                  {caseStudy.experts} {t("common.experts")}
                </span>
                <span className="mx-2">•</span>
                <span>{caseStudy.dataType === "interval" ? t("common.intervalScale") : t("common.likertScale")}</span>
              </div>
            </div>

            <h1 className="font-display text-3xl md:text-5xl font-normal mb-4">
              {caseStudy.title}
            </h1>
            <p className="text-lg text-muted-foreground max-w-3xl">
              {caseStudy.fullDescription}
            </p>
          </motion.div>
        </div>
      </section>

      {/* Main Content */}
      <section className="py-12 md:py-16">
        <div className="container mx-auto px-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column - Question & Context */}
            <div className="lg:col-span-2 space-y-8">
              {/* Question Card */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.5 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Target className="h-5 w-5" />
                      {t("common.question")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <blockquote className="border-l-4 border-primary/30 pl-4 italic text-muted-foreground">
                      "{caseStudy.question}"
                    </blockquote>
                    <div className="mt-4 flex items-center gap-4 text-sm">
                      <span className="px-3 py-1 bg-secondary rounded-full">
                        {t("common.scale")}: {caseStudy.scaleMin}–{caseStudy.scaleMax}{" "}
                        {caseStudy.scaleUnit}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Context Card */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.5 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Info className="h-5 w-5" />
                      {t("common.context")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-muted-foreground">{caseStudy.context}</p>
                    <div className="pt-4 border-t">
                      <h3 className="font-medium text-base mb-2">
                        {t("common.methodology")}
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        {caseStudy.methodology}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>

              {/* Expert Opinions Table */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.5 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Users className="h-5 w-5" />
                      {t("common.expertOpinions")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <caption className="sr-only">
                          {t("common.expertOpinions")} — {caseStudy.title}
                        </caption>
                        <thead>
                          <tr className="border-b">
                            <th scope="col" className="text-left py-3 px-2 font-medium">
                              {t("common.role")}
                            </th>
                            {caseStudy.dataType === "interval" ? (
                              <>
                                <th scope="col" className="text-right py-3 px-2 font-medium">
                                  {t("common.lowerLimit")}
                                </th>
                                <th scope="col" className="text-right py-3 px-2 font-medium">
                                  {t("common.bestProposal")}
                                </th>
                                <th scope="col" className="text-right py-3 px-2 font-medium">
                                  {t("common.upperLimit")}
                                </th>
                              </>
                            ) : (
                              <>
                                <th scope="col" className="text-right py-3 px-2 font-medium">
                                  {t("common.value")}
                                </th>
                                <th scope="col" className="text-left py-3 px-2 font-medium">
                                  {t("common.label")}
                                </th>
                              </>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {caseStudy.dataType === "interval"
                            ? caseStudy.opinions.map((opinion, index) => (
                                <tr
                                  key={`${opinion.role}-${index}`}
                                  className="border-b last:border-0 hover:bg-secondary/50 transition-colors"
                                >
                                  <td className="py-3 px-2">{opinion.role}</td>
                                  <td className="text-right py-3 px-2 font-mono">
                                    {opinion.lowerLimit}
                                  </td>
                                  <td className="text-right py-3 px-2 font-mono font-medium">
                                    {opinion.bestProposal}
                                  </td>
                                  <td className="text-right py-3 px-2 font-mono">
                                    {opinion.upperLimit}
                                  </td>
                                </tr>
                              ))
                            : caseStudy.opinions.map((opinion, index) => (
                                <LikertRow
                                  key={`${opinion.role}-${index}`}
                                  role={opinion.role}
                                  value={opinion.value}
                                />
                              ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            </div>

            {/* Right Column - Results */}
            <div className="space-y-6">
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2, duration: 0.5 }}
                className="sticky top-24"
              >
                <Card className="bg-primary text-primary-foreground">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <BarChart3 className="h-5 w-5" />
                      {t("common.results")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div>
                      <div className="text-sm opacity-80 mb-1">
                        {t("common.bestCompromise")}
                      </div>
                      <div className="text-4xl font-mono font-bold">
                        {caseStudy.result.bestCompromise}
                        <span className="text-lg ml-1 opacity-80">
                          {caseStudy.scaleUnit}
                        </span>
                      </div>
                    </div>

                    <div>
                      <div className="text-sm opacity-80 mb-1">
                        {t("common.maxError")}
                      </div>
                      <div className="text-2xl font-mono">
                        ±{caseStudy.result.maxError}
                        <span className="text-sm ml-1 opacity-80">
                          {caseStudy.scaleUnit}
                        </span>
                      </div>
                    </div>

                    {caseStudy.dataType !== "interval" && (
                      <LikertInterpretation
                        value={caseStudy.result.bestCompromise}
                      />
                    )}
                  </CardContent>
                </Card>

                <Card className="mt-6">
                  <CardHeader>
                    <CardTitle className="text-lg">
                      {t("common.interpretation")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {caseStudy.result.interpretation}
                    </p>
                  </CardContent>
                </Card>

                {/* Visual representation for interval data */}
                {caseStudy.dataType === "interval" && (
                  <Card className="mt-6">
                    <CardHeader>
                      <CardTitle className="text-lg">
                        {t("common.opinionDistribution")}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {caseStudy.opinions.slice(0, 8).map((opinion, index) => {
                          const range =
                            caseStudy.scaleMax - caseStudy.scaleMin;
                          const leftPct =
                            ((opinion.lowerLimit - caseStudy.scaleMin) /
                              range) *
                            100;
                          const widthPct =
                            ((opinion.upperLimit - opinion.lowerLimit) /
                              range) *
                            100;
                          const peakPct =
                            ((opinion.bestProposal - caseStudy.scaleMin) /
                              range) *
                            100;

                          return (
                            <div
                              key={`${opinion.role}-${index}`}
                              className="relative h-6"
                              data-testid="opinion-bar"
                            >
                              <div
                                className="absolute h-2 bg-secondary rounded-full top-2"
                                style={{
                                  left: `${leftPct}%`,
                                  width: `${widthPct}%`,
                                }}
                              />
                              <div
                                className="absolute w-2 h-2 bg-primary rounded-full top-2"
                                style={{ left: `${peakPct}%` }}
                              />
                            </div>
                          );
                        })}
                        <div className="flex justify-between text-xs mt-2 pt-2 border-t">
                          <span className="text-muted-foreground">
                            {caseStudy.scaleMin} {caseStudy.scaleUnit}
                          </span>
                          <span className="text-muted-foreground">
                            {caseStudy.scaleMax} {caseStudy.scaleUnit}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </motion.div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-secondary/30">
        <div className="container mx-auto px-6 text-center">
          <h2 className="font-display text-2xl md:text-3xl font-normal mb-4">
            {t("common.ctaTitle")}
          </h2>
          <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
            {t("common.ctaDescription")}
          </p>
          <Button size="lg" asChild>
            <Link to="/register">{tCommon("nav.getStarted")}</Link>
          </Button>
        </div>
      </section>

      </main>
      <Footer />
    </div>
  );
};

function LikertRow({ role, value }: { readonly role: string; readonly value: number }) {
  const label = useLocalizedLikertLabel(value);
  return (
    <tr className="border-b last:border-0 hover:bg-secondary/50 transition-colors">
      <td className="py-3 px-2">{role}</td>
      <td className="text-right py-3 px-2 font-mono font-medium">{value}</td>
      <td className="py-3 px-2 text-muted-foreground">{label}</td>
    </tr>
  );
}

function LikertInterpretation({ value }: { readonly value: number }) {
  const { t } = useTranslation("caseStudies");
  const label = useLocalizedLikertLabel(value);
  return (
    <div>
      <div className="text-sm opacity-80 mb-1">{t("common.likertInterpretation")}</div>
      <div className="text-xl font-medium">{label}</div>
    </div>
  );
}

export default CaseStudy;
