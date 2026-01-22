import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { FuzzyTriangleSVG } from "@/components/visualizations/FuzzyTriangleSVG";
import { ArrowRight, Users, Calculator, Target } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { caseStudies } from "@/data/caseStudies";

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
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      
      {/* Hero Section */}
      <section className="pt-32 pb-20 md:pt-40 md:pb-32">
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
              Group Decisions,
              <br />
              <span className="font-medium">Precisely Measured</span>
            </motion.h1>
            
            <motion.p 
              className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10"
              variants={fadeInUp}
            >
              Aggregate expert opinions using fuzzy triangular numbers. 
              Find the best compromise through mathematical consensus.
            </motion.p>
            
            <motion.div variants={fadeInUp}>
              <Link to={isAuthenticated ? "/projects" : "/register"}>
                <Button size="lg" className="gap-2">
                  {isAuthenticated ? "Go to Projects" : "Start Your Project"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
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
              How It Works
            </h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              A three-step process to find consensus among experts
            </p>
          </motion.div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                icon: Users,
                title: "Collect",
                description: "Experts provide their estimates as fuzzy triangular numbers (lower, peak, upper)"
              },
              {
                icon: Calculator,
                title: "Calculate",
                description: "System computes arithmetic mean, median, and identifies the best compromise"
              },
              {
                icon: Target,
                title: "Consensus",
                description: "Get the optimal decision with error estimation and confidence metrics"
              }
            ].map((step, index) => (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
              >
                <Card className="h-full border-border/50 hover:border-border transition-colors">
                  <CardContent className="pt-8 pb-8 text-center">
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
                      <step.icon className="h-6 w-6" />
                    </div>
                    <h3 className="font-display text-xl font-medium mb-3">
                      {step.title}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {step.description}
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
            <Link to="/about" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Learn more about the BeCoMe method →
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Case Studies */}
      <section className="py-20 md:py-32">
        <div className="container mx-auto px-6">
          <motion.div 
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="font-display text-3xl md:text-4xl font-normal mb-4">
              Case Studies
            </h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              Real-world applications of the BeCoMe methodology
            </p>
          </motion.div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {caseStudies.map((study, index) => (
              <motion.div
                key={study.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
              >
                <Link to={`/case-study/${study.id}`}>
                  <Card className="h-full group hover:shadow-md hover:border-primary/30 transition-all duration-200 cursor-pointer">
                    <CardContent className="pt-6 pb-6">
                      <div className="flex items-start gap-4">
                        <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                          <study.icon className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                        </div>
                        <div>
                          <h3 className="font-medium text-base mb-1 group-hover:text-primary transition-colors">
                            {study.title}
                          </h3>
                          <p className="text-sm text-muted-foreground mb-3">
                            {study.description}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Users className="h-3 w-3" />
                            <span className="font-mono">{study.experts} experts</span>
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

      {/* CTA Section */}
      <section className="py-20 md:py-32 bg-primary text-primary-foreground">
        <div className="container mx-auto px-6">
          <motion.div 
            className="max-w-2xl mx-auto text-center"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="font-display text-3xl md:text-4xl font-normal mb-6">
              Ready to find consensus?
            </h2>
            <p className="text-primary-foreground/80 mb-8">
              Create your first project and start collecting expert opinions today.
            </p>
            <Link to={isAuthenticated ? "/projects" : "/register"}>
              <Button 
                variant="secondary" 
                size="lg" 
                className="gap-2"
              >
                Get Started Free
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </motion.div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Landing;
