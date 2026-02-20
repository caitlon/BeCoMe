import { useCallback, useEffect, useState } from "react";

/**
 * Tracks which section is currently visible in the viewport.
 * Returns the ID of the active section and a function to smooth-scroll to a section.
 *
 * Callers should pass a stable array reference for `sectionIds`
 * (module-level constant or wrapped in useMemo) to avoid re-subscribing on every render.
 */
export function useScrollSpy(sectionIds: readonly string[], defaultId: string) {
  const [activeId, setActiveId] = useState(defaultId);

  useEffect(() => {
    const handleScroll = () => {
      for (const id of sectionIds) {
        const element = document.getElementById(id);
        if (element) {
          const rect = element.getBoundingClientRect();
          if (rect.top <= 150 && rect.bottom >= 150) {
            setActiveId(id);
            break;
          }
        }
      }
    };

    globalThis.addEventListener("scroll", handleScroll);
    handleScroll();
    return () => globalThis.removeEventListener("scroll", handleScroll);
  }, [sectionIds]);

  const scrollToSection = useCallback((id: string) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 100;
      const top =
        element.getBoundingClientRect().top + globalThis.scrollY - offset;
      globalThis.scrollTo({ top, behavior: "smooth" });
    }
  }, []);

  return { activeId, scrollToSection } as const;
}
