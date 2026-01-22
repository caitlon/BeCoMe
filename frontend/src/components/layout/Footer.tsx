import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-border bg-card">
      <div className="container mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Logo & Description */}
          <div className="md:col-span-2">
            <Link to="/" className="font-display text-xl font-medium">
              BeCoMe
            </Link>
            <p className="mt-3 text-sm text-muted-foreground max-w-md">
              {t("footer.description")}
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="font-medium text-sm mb-4">{t("footer.product")}</h4>
            <ul className="space-y-2">
              <li>
                <Link
                  to="/register"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("nav.getStarted")}
                </Link>
              </li>
              <li>
                <Link
                  to="/login"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("nav.signIn")}
                </Link>
              </li>
            </ul>
          </div>

          {/* Authors */}
          <div>
            <h4 className="font-medium text-sm mb-4">
              {t("footer.methodAuthors")}
            </h4>
            <ul className="space-y-2">
              <li>
                <span className="text-sm text-muted-foreground">
                  Prof. Ing. Ivan Vrana, DrSc.
                </span>
              </li>
              <li>
                <span className="text-sm text-muted-foreground">
                  Ing. Jan Tyrychtr, PhD.
                </span>
              </li>
              <li>
                <span className="text-sm text-muted-foreground mt-2 block">
                  CZU Prague
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} BeCoMe. {t("footer.copyright")}
          </p>
          <p className="text-sm text-muted-foreground">{t("footer.methodBy")}</p>
        </div>
      </div>
    </footer>
  );
}
