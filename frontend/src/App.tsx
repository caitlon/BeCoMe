import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { RouteAnnouncer } from "@/components/RouteAnnouncer";
import { Loader2 } from "lucide-react";

const Landing = lazy(() => import("./pages/Landing"));
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const Projects = lazy(() => import("./pages/Projects"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail"));
const Profile = lazy(() => import("./pages/Profile"));
const CaseStudies = lazy(() => import("./pages/CaseStudies"));
const CaseStudy = lazy(() => import("./pages/CaseStudy"));
const About = lazy(() => import("./pages/About"));
const Documentation = lazy(() => import("./pages/Documentation"));
const FaqPage = lazy(() => import("./pages/FAQ"));
const Onboarding = lazy(() => import("./pages/Onboarding"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = new QueryClient();

function PageLoader() {
  const { t } = useTranslation();
  return (
    <main id="main-content" tabIndex={-1} className="min-h-screen flex items-center justify-center">
      <output>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="sr-only">{t("common.loading")}</span>
      </output>
    </main>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <RouteAnnouncer />
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/about" element={<About />} />
              <Route path="/docs" element={<Documentation />} />
              <Route path="/faq" element={<FaqPage />} />
              <Route path="/case-studies" element={<CaseStudies />} />
              <Route path="/case-study/:id" element={<CaseStudy />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/projects" element={
                <ProtectedRoute>
                  <Projects />
                </ProtectedRoute>
              } />
              <Route path="/projects/:id" element={
                <ProtectedRoute>
                  <ProjectDetail />
                </ProtectedRoute>
              } />
              <Route path="/profile" element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              } />
              <Route path="/onboarding" element={
                <ProtectedRoute>
                  <Onboarding />
                </ProtectedRoute>
              } />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
