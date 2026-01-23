import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function FooterMinimal() {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-border bg-card py-6">
      <div className="container mx-auto px-6">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="font-display text-lg font-medium">
              {t("brand.name")}
            </Link>
            <nav className="flex items-center gap-4">
              <Link
                to="/about"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.about")}
              </Link>
              <a
                href="https://github.com/caitlon/BeCoMe"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("footer.github")}
              </a>
            </nav>
          </div>
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} {t("brand.name")}. {t("footer.copyright")}
          </p>
        </div>
      </div>
    </footer>
  );
}
