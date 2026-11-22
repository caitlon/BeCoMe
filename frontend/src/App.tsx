import { lazy, Suspense, type ComponentType, type ReactNode } from "react";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { BrowserRouter, Routes, Route } from "react-router";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { GuestRoute } from "@/components/auth/GuestRoute";
import { RouteAnnouncer } from "@/components/RouteAnnouncer";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PageLoader } from "@/components/PageLoader";
import { createQueryClient } from "@/lib/queryClient";
import { AssistantProvider, AssistantEntry } from "@/components/assistant";

const Landing = lazy(() => import("./pages/Landing"));
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const ResetPassword = lazy(() => import("./pages/ResetPassword"));
const VerifyEmail = lazy(() => import("./pages/VerifyEmail"));
const Projects = lazy(() => import("./pages/Projects"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail"));
const Profile = lazy(() => import("./pages/Profile"));
const CaseStudies = lazy(() => import("./pages/CaseStudies"));
const CaseStudy = lazy(() => import("./pages/CaseStudy"));
const About = lazy(() => import("./pages/About"));
const Documentation = lazy(() => import("./pages/Documentation"));
const FaqPage = lazy(() => import("./pages/FAQ"));
const Privacy = lazy(() => import("./pages/Privacy"));
const Terms = lazy(() => import("./pages/Terms"));
const Onboarding = lazy(() => import("./pages/Onboarding"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = createQueryClient();

interface AppWithRouterProps {
  /** Wraps the routed tree: the browser router on the client, a static one on the server. */
  readonly Router: ComponentType<{ children: ReactNode }>;
}

/** The whole app below the theme provider, with the router supplied by the caller. */
export const AppWithRouter = ({ Router }: AppWithRouterProps) => (
  <ErrorBoundary>
    <MotionConfig reducedMotion="user">
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TooltipProvider>
            <AssistantProvider>
              <Toaster />
              <Router>
                <RouteAnnouncer />
                <Suspense fallback={<PageLoader />}>
                  <ErrorBoundary>
                    <Routes>
                      <Route path="/" element={<Landing />} />
                      <Route path="/about" element={<About />} />
                      <Route path="/docs" element={<Documentation />} />
                      <Route path="/faq" element={<FaqPage />} />
                      <Route path="/privacy" element={<Privacy />} />
                      <Route path="/terms" element={<Terms />} />
                      <Route path="/case-studies" element={<CaseStudies />} />
                      <Route path="/case-study/:id" element={<CaseStudy />} />
                      <Route path="/login" element={
                        <GuestRoute>
                          <Login />
                        </GuestRoute>
                      } />
                      <Route path="/register" element={
                        <GuestRoute>
                          <Register />
                        </GuestRoute>
                      } />
                      <Route path="/forgot-password" element={<ForgotPassword />} />
                      <Route path="/reset-password" element={<ResetPassword />} />
                      <Route path="/verify-email" element={<VerifyEmail />} />
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
                  </ErrorBoundary>
                </Suspense>
                {AssistantEntry && (
                  <ErrorBoundary fallback={null}>
                    <Suspense fallback={null}>
                      <AssistantEntry />
                    </Suspense>
                  </ErrorBoundary>
                )}
              </Router>
            </AssistantProvider>
          </TooltipProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MotionConfig>
  </ErrorBoundary>
);

const App = () => <AppWithRouter Router={BrowserRouter} />;

export default App;
