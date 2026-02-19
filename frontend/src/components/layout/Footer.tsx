import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MessageSquare } from "lucide-react";

export function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-border bg-card">
      <div className="container mx-auto px-6 py-12">
        {/* Logo & Description */}
        <div className="mb-8">
          <Link to="/" className="font-display text-xl font-medium">
            {t("brand.name")}
          </Link>
          <p className="mt-3 text-sm text-muted-foreground">
            {t("footer.description")}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            <a
              href="https://www.linkedin.com/in/kuzmina-ekaterina/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground hover:underline"
            >
              {t("footer.authorName")}
            </a>
            {" – "}
            {t("footer.implementationThesis")}
            {", "}
            {t("footer.implementationUniversity")}
          </p>
        </div>

        {/* 3-column grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          {/* Product */}
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
              <li>
                <Link
                  to="/about"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("nav.about")}
                </Link>
              </li>
              <li>
                <Link
                  to="/case-studies"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("footer.caseStudies")}
                </Link>
              </li>
            </ul>
          </div>

          {/* Method Authors */}
          <div>
            <h4 className="font-medium text-sm mb-4">
              {t("footer.methodAuthors")}
            </h4>
            <ul className="space-y-2">
              <li>
                <span className="text-sm text-muted-foreground">
                  {t("footer.vrana")}
                </span>
              </li>
              <li>
                <span className="text-sm text-muted-foreground">
                  {t("footer.tyrychtr")}
                </span>
              </li>
              <li>
                <span className="text-sm text-muted-foreground">
                  {t("footer.pelikan")}
                </span>
              </li>
              <li>
                <a
                  href="https://www.czu.cz"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors mt-2 block"
                >
                  {t("footer.czuPrague")}
                </a>
              </li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="font-medium text-sm mb-4">
              {t("footer.resources")}
            </h4>
            <ul className="space-y-2">
              <li>
                <a
                  href="https://github.com/caitlon/BeCoMe"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("footer.github")}
                </a>
              </li>
              <li>
                <Link
                  to="/docs"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("footer.documentation")}
                </Link>
              </li>
              <li>
                <Link
                  to="/faq"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t("footer.faq")}
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Feedback section */}
        <div className="text-center mb-8 pb-8 border-b border-border">
          <div className="flex items-center justify-center gap-2 mb-2">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <h4 className="font-medium text-sm">{t("footer.feedback")}</h4>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("footer.feedbackText")}{" "}
            <a
              href="https://github.com/caitlon/BeCoMe/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground hover:underline"
            >
              {t("footer.github")}
            </a>
          </p>
        </div>

        {/* Copyright */}
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} {t("brand.name")}. {t("footer.copyright")}
          </p>
          <p className="text-sm text-muted-foreground">{t("footer.methodBy")}</p>
        </div>
      </div>
    </footer>
  );
}
