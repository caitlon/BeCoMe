import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";

const languages = [
  { code: "en", label: "EN", name: "English" },
  { code: "cs", label: "CS", name: "Čeština" },
] as const;

export function LanguageSwitcher() {
  const { i18n } = useTranslation();

  const resolved = (i18n.resolvedLanguage ?? i18n.language).split("-")[0];
  const currentLang = resolved === "cs" ? "cs" : "en";
  const nextLang = currentLang === "en" ? languages[1] : languages[0];

  const toggleLanguage = () => {
    i18n.changeLanguage(nextLang.code);
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleLanguage}
      className="h-10 px-3 hover:bg-muted transition-colors duration-300"
      aria-label={`Switch to ${nextLang.name}`}
    >
      <span className="text-sm font-medium">
        {currentLang.toUpperCase()}
      </span>
    </Button>
  );
}
