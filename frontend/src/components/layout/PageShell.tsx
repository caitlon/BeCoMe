import { cn } from "@/lib/utils";
import { Footer } from "@/components/layout/Footer";
import { Navbar } from "@/components/layout/Navbar";

/**
 * "app" hangs the shared container and the offset that clears the fixed navbar
 * on <main>. "content" leaves spacing to the page's own <section>s, which is how
 * the marketing and documentation pages are built. "centered" is the single-block
 * layout the loading and error states use.
 */
type PageShellVariant = "app" | "content" | "centered";

const MAIN_CLASSES: Record<PageShellVariant, string> = {
  app: "container mx-auto px-6 pt-24 pb-16",
  content: "",
  centered: "pt-24 flex items-center justify-center",
};

interface PageShellProps {
  readonly variant?: PageShellVariant;
  readonly footer?: boolean;
  /** Appended to the variant's own classes, not a replacement for them. */
  readonly mainClassName?: string;
  /**
   * Rendered between the navbar and <main>. For fixed page chrome that sits
   * outside the content landmark. Onboarding's progress bar is the one case.
   */
  readonly beforeMain?: React.ReactNode;
  /** Rendered after </main>, for fixed chrome that belongs below the content. */
  readonly afterMain?: React.ReactNode;
  readonly children: React.ReactNode;
}

/**
 * The page frame every route shares: the background, the navbar, the
 * `#main-content` landmark that RouteAnnouncer moves focus to, and optionally
 * the footer. Loading and error branches go through it too, since building them by
 * hand is how they ended up on a different background than the loaded page.
 */
export function PageShell({
  variant = "app",
  footer = false,
  mainClassName,
  beforeMain,
  afterMain,
  children,
}: PageShellProps) {
  return (
    <div className={cn("min-h-screen bg-background", variant === "content" && "flex flex-col")}>
      <Navbar />
      {beforeMain}
      <main id="main-content" className={cn(MAIN_CLASSES[variant], mainClassName)}>
        {children}
      </main>
      {afterMain}
      {footer && <Footer />}
    </div>
  );
}
