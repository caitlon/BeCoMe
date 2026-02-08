import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useAuth } from "@/contexts/AuthContext";
import { useState, useEffect, useCallback } from "react";
import { Menu, X, ChevronDown, User, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function Navbar() {
  const { t } = useTranslation();
  const { t: tOnboarding } = useTranslation("onboarding");
  const { isAuthenticated, user, logout } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleLogout = () => {
    logout();
    window.location.href = '/';
  };

  const closeMenuOnEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape" && isMenuOpen) {
      setIsMenuOpen(false);
    }
  }, [isMenuOpen]);

  useEffect(() => {
    document.addEventListener("keydown", closeMenuOnEscape);
    return () => document.removeEventListener("keydown", closeMenuOnEscape);
  }, [closeMenuOnEscape]);

  const isAuthPage = ['/login', '/register'].includes(location.pathname);

  return (
    <nav
      aria-label={t("a11y.mainNavigation")}
      className={cn(
        "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
        isScrolled
          ? "bg-background/80 backdrop-blur-md border-b border-border shadow-sm"
          : "bg-background/95 backdrop-blur-sm border-b border-transparent"
      )}
    >
      <div className="container mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link
          to={isAuthenticated ? "/projects" : "/"}
          className="font-display text-2xl font-medium tracking-tight"
        >
          BeCoMe
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-6">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/about" aria-current={location.pathname === "/about" ? "page" : undefined}>{t("nav.about")}</Link>
          </Button>
          {isAuthenticated ? (
            <>
              <Link
                to="/projects"
                aria-current={location.pathname === "/projects" ? "page" : undefined}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.projects")}
              </Link>
              <Link
                to="/onboarding"
                aria-current={location.pathname === "/onboarding" ? "page" : undefined}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {tOnboarding("navbar.takeTour")}
              </Link>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="gap-2">
                    <span className="text-sm">
                      {user?.first_name} {user?.last_name}
                    </span>
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem asChild>
                    <Link to="/profile" className="cursor-pointer">
                      <User className="mr-2 h-4 w-4" />
                      {t("nav.profile")}
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={handleLogout}
                    className="cursor-pointer text-destructive"
                  >
                    <LogOut className="mr-2 h-4 w-4" />
                    {t("nav.signOut")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : !isAuthPage && (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/login">{t("nav.signIn")}</Link>
              </Button>
              <Button size="sm" asChild>
                <Link to="/register">{t("nav.getStarted")}</Link>
              </Button>
            </>
          )}

          <LanguageSwitcher />
          <ThemeToggle />
        </div>

        {/* Mobile Menu Button */}
        <div className="md:hidden flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
          {!isAuthPage && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              aria-expanded={isMenuOpen}
              aria-controls="mobile-menu"
              aria-label={isMenuOpen ? t("a11y.closeMenu") : t("a11y.openMenu")}
            >
              {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          )}
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isMenuOpen && !isAuthPage && (
          <motion.div
            id="mobile-menu"
            role="navigation"
            aria-label={t("a11y.mobileNavigation")}
            className="md:hidden bg-background/95 backdrop-blur-md border-b border-border"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="container mx-auto px-6 py-4 space-y-3">
            <Link
              to="/about"
              aria-current={location.pathname === "/about" ? "page" : undefined}
              className="block py-2 text-muted-foreground hover:text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              {t("nav.about")}
            </Link>
            {isAuthenticated ? (
              <>
                <Link
                  to="/projects"
                  aria-current={location.pathname === "/projects" ? "page" : undefined}
                  className="block py-2 text-muted-foreground hover:text-foreground"
                  onClick={() => setIsMenuOpen(false)}
                >
                  {t("nav.projects")}
                </Link>
                <Link
                  to="/onboarding"
                  aria-current={location.pathname === "/onboarding" ? "page" : undefined}
                  className="block py-2 text-muted-foreground hover:text-foreground"
                  onClick={() => setIsMenuOpen(false)}
                >
                  {tOnboarding("navbar.takeTour")}
                </Link>
                <Link
                  to="/profile"
                  aria-current={location.pathname === "/profile" ? "page" : undefined}
                  className="block py-2 text-muted-foreground hover:text-foreground"
                  onClick={() => setIsMenuOpen(false)}
                >
                  {t("nav.profile")}
                </Link>
                <button
                  onClick={handleLogout}
                  className="block py-2 text-destructive hover:text-destructive/80 w-full text-left"
                >
                  {t("nav.signOut")}
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="block py-2 text-muted-foreground hover:text-foreground"
                  onClick={() => setIsMenuOpen(false)}
                >
                  {t("nav.signIn")}
                </Link>
                <Button className="w-full" asChild>
                  <Link to="/register" onClick={() => setIsMenuOpen(false)}>
                    {t("nav.getStarted")}
                  </Link>
                </Button>
              </>
            )}
          </div>
        </motion.div>
      )}
      </AnimatePresence>
    </nav>
  );
}
