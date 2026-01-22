import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, BookOpen, Users, Calculator, BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

const About = () => {
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
              About BeCoMe
            </h1>
            <p className="text-lg text-muted-foreground">
              Best Compromise Mean — a scientific method for optimal group
              decision-making under fuzzy uncertainty.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Introduction */}
      <section className="py-12 md:py-16">
        <div className="container mx-auto px-6">
          <div className="max-w-3xl">
            <motion.div {...fadeInUp}>
              <h2 className="font-display text-2xl md:text-3xl font-normal mb-6">
                The Challenge
              </h2>
              <div className="prose prose-neutral dark:prose-invert">
                <p className="text-muted-foreground leading-relaxed mb-4">
                  Real-world systems are influenced by many ambiguous
                  circumstances, which complicates planning, modelling,
                  prediction, and decision-making. Decision-making procedures
                  often rely on the opinions of experts who express their
                  standpoints from their own perspective.
                </p>
                <p className="text-muted-foreground leading-relaxed mb-4">
                  Depending on the structure of expert teams, experts' opinions
                  can vary broadly or may even contradict each other. Finding
                  the best possible compromise of experts' opinions is a basic
                  need in such situations.
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
                The BeCoMe Method
              </h2>
              <div className="prose prose-neutral dark:prose-invert">
                <p className="text-muted-foreground leading-relaxed mb-4">
                  Over many years of research at Czech University of Life
                  Sciences in Prague (CZU), researchers developed the unique
                  BeCoMe (Best-Compromise-Mean) method for determining the
                  optimum group decision, which corresponds to the best
                  compromise/agreement of all experts' opinions.
                </p>
                <p className="text-muted-foreground leading-relaxed">
                  The optimum decision is a result of a computationally complex
                  fuzzy set mathematical model based on minimizing entropy. This
                  approach ensures that the final decision represents the most
                  balanced compromise among all expert viewpoints.
                </p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* How Experts Express Opinions */}
      <section className="py-12 md:py-16">
        <div className="container mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="mb-10"
          >
            <h2 className="font-display text-2xl md:text-3xl font-normal mb-4">
              How Experts Express Their Opinions
            </h2>
            <p className="text-muted-foreground max-w-3xl">
              Experts answer the raised question and assess a certain
              quantitative parameter of the proposed solution. They can express
              their responses in three ways:
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl">
            {[
              {
                icon: Calculator,
                title: "Crisp Number",
                description:
                  "A single precise value when the expert is confident about their estimate.",
                example: "Example: 50 billion CZK",
              },
              {
                icon: BarChart3,
                title: "Fuzzy Interval",
                description:
                  "A triangular membership function with three values: best proposal, lower limit, and upper limit.",
                example: "Example: (40, 60, 80) — pessimistic, most likely, optimistic",
              },
              {
                icon: Users,
                title: "Likert Scale",
                description:
                  "Linguistic terms mapped to numeric values: Strongly disagree (0), Rather disagree (25), Neutral (50), Rather agree (75), Strongly agree (100).",
                example: "Example: Rather agree = 75",
              },
            ].map((method, index) => (
              <motion.div
                key={method.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
              >
                <Card className="h-full">
                  <CardHeader>
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-3">
                      <method.icon className="h-5 w-5 text-primary" />
                    </div>
                    <CardTitle className="text-lg">{method.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground mb-3">
                      {method.description}
                    </p>
                    <p className="text-xs font-mono text-muted-foreground/70">
                      {method.example}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Results */}
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
                Results
              </h2>
              <div className="space-y-4">
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-medium shrink-0">
                    1
                  </div>
                  <div>
                    <h3 className="font-medium mb-1">Best Compromise</h3>
                    <p className="text-sm text-muted-foreground">
                      The optimal value that represents the best agreement among
                      all expert opinions, calculated through fuzzy set
                      mathematics.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-medium shrink-0">
                    2
                  </div>
                  <div>
                    <h3 className="font-medium mb-1">Maximum Error of Estimate</h3>
                    <p className="text-sm text-muted-foreground">
                      A quality metric that indicates the uncertainty level of
                      the compromise, helping decision-makers understand the
                      confidence in the result.
                    </p>
                  </div>
                </div>
              </div>
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
                Applications
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-6">
                The BeCoMe method is a unique, helpful, and easily available
                instrument in many decision-making situations:
              </p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  "State security decisions",
                  "Public health policy",
                  "Investment planning",
                  "Flood prevention",
                  "Energy self-sufficiency",
                  "IT contract evaluation",
                  "Budget allocation",
                  "Risk assessment",
                ].map((app) => (
                  <li
                    key={app}
                    className="flex items-center gap-2 text-muted-foreground"
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                    {app}
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
              Authors
            </h2>
            <Card className="max-w-xl">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-secondary flex items-center justify-center">
                    <BookOpen className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="font-medium">
                      Prof. Ing. Ivan Vrana, DrSc.
                    </p>
                    <p className="font-medium">Ing. Jan Tyrychtr, PhD.</p>
                    <p className="text-sm text-muted-foreground mt-2">
                      Department of Information Engineering
                      <br />
                      Faculty of Economics and Management
                      <br />
                      Czech University of Life Sciences Prague
                    </p>
                  </div>
                </div>
                <div className="mt-6 pt-4 border-t">
                  <p className="text-xs text-muted-foreground">
                    <strong>Citation:</strong> Vrana, I., Tyrychtr, J. (2020).
                    BeCoMe-FuzzyDecisionTool, CZU Prague.
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
            See BeCoMe in Action
          </h2>
          <p className="text-primary-foreground/80 mb-8 max-w-xl mx-auto">
            Explore real-world case studies or start your own project.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/">
              <Button variant="secondary" size="lg">
                View Case Studies
              </Button>
            </Link>
            <Link to="/register">
              <Button
                variant="outline"
                size="lg"
                className="gap-2 bg-transparent border-primary-foreground/30 text-primary-foreground hover:bg-primary-foreground/10"
              >
                Start Your Project
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default About;
