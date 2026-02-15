import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useAuth } from "@/contexts/AuthContext";
import { useState, useEffect, useCallback, useRef } from "react";
import { Menu, X, ChevronDown, User, LogOut } from "lucide-react";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
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
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(globalThis.scrollY > 10);
    };
    globalThis.addEventListener("scroll", handleScroll, { passive: true });
    return () => globalThis.removeEventListener("scroll", handleScroll);
  }, []);

  const handleLogout = () => {
    logout();
    globalThis.location.href = '/';
  };

  const closeMenuOnEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") {
      setIsMenuOpen((open) => {
        if (open) menuButtonRef.current?.focus();
        return false;
      });
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", closeMenuOnEscape);
    return () => document.removeEventListener("keydown", closeMenuOnEscape);
  }, [closeMenuOnEscape]);

  const isAuthPage = ['/login', '/register'].includes(location.pathname);

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + "/");

  const navItems = [
    { to: "/about", label: t("nav.about") },
    { to: "/docs", label: t("nav.docs") },
    { to: "/faq", label: t("nav.faq") },
    { to: "/case-studies", label: t("nav.caseStudies") },
  ];

  const authNavItems = [
    { to: "/projects", label: t("nav.projects") },
    { to: "/onboarding", label: tOnboarding("navbar.takeTour") },
  ];

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
          to="/"
          className="font-display text-2xl font-medium tracking-tight"
        >
          BeCoMe
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-6">
          {navItems.map(({ to, label }) => (
            <Button key={to} variant="ghost" size="sm" className={cn(isActive(to) && "text-foreground border-b-2 border-primary rounded-none")} asChild>
              <Link to={to} aria-current={isActive(to) ? "page" : undefined}>{label}</Link>
            </Button>
          ))}
          {isAuthenticated ? (
            <>
              {authNavItems.map(({ to, label }) => (
                <Button key={to} variant="ghost" size="sm" className={cn(isActive(to) && "text-foreground border-b-2 border-primary rounded-none")} asChild>
                  <Link to={to} aria-current={isActive(to) ? "page" : undefined}>{label}</Link>
                </Button>
              ))}

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="gap-2">
                    <Avatar className="h-7 w-7" aria-hidden="true">
                      {user?.photo_url && (
                        <AvatarImage src={user.photo_url} alt="" />
                      )}
                      <AvatarFallback className="text-xs">
                        {user ? `${user.first_name[0]}${user.last_name?.[0] || ""}`.toUpperCase() : ""}
                      </AvatarFallback>
                    </Avatar>
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
              ref={menuButtonRef}
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
            role="region"
            aria-label={t("a11y.mobileNavigation")}
            className="md:hidden bg-background/95 backdrop-blur-md border-b border-border"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="container mx-auto px-6 py-4 space-y-3">
            {navItems.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                aria-current={isActive(to) ? "page" : undefined}
                className={cn("block py-2 hover:text-foreground", isActive(to) ? "text-foreground font-medium" : "text-muted-foreground")}
                onClick={() => setIsMenuOpen(false)}
              >
                {label}
              </Link>
            ))}
            {isAuthenticated ? (
              <>
                {[...authNavItems, { to: "/profile", label: t("nav.profile") }].map(({ to, label }) => (
                  <Link
                    key={to}
                    to={to}
                    aria-current={isActive(to) ? "page" : undefined}
                    className={cn("block py-2 hover:text-foreground", isActive(to) ? "text-foreground font-medium" : "text-muted-foreground")}
                    onClick={() => setIsMenuOpen(false)}
                  >
                    {label}
                  </Link>
                ))}
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
