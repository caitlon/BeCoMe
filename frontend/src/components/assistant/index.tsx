import { lazy, Suspense, useEffect, useState, type ComponentType, type LazyExoticComponent, type ReactNode } from "react";
import * as Sentry from "@sentry/react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AssistantUIProvider, useAssistantUI } from "@/contexts/AssistantUIContext";
import { logger } from "@/lib/logger";

/**
 * Build-time kill switch for the whole assistant feature,
 * computed once so every export below shares the same answer. Vite
 * statically replaces `import.meta.env.VITE_ASSISTANT_ENABLED` with a
 * literal at build time, so when it is not exactly "true" every branch below
 * is unreachable and `vite build`'s dead-code elimination drops the dynamic
 * `import()` calls together with it -- none of the AssistantRoot chunk, the
 * triggers chunk (buttons, assistant.json content, every /api/v1/assistant/*
 * path), the profile privacy card chunk and the documentation guide chunk
 * reaches `dist/`. That only holds for
 * `vite build`; `vite dev` serves unbundled ESM and never tree-shakes. The
 * real check is a production build plus a grep of `dist/assets` for the
 * chunk names.
 *
 * Only a build with the variable set to exactly `true` includes the
 * assistant: a developer's own frontend/.env.development.local (gitignored
 * via the repo's `*.local` pattern), or the dev and test frontend services,
 * which pass it through frontend/Dockerfile. Prod leaves it unset, so its
 * build takes the disabled branch below.
 */
const enabled = import.meta.env.VITE_ASSISTANT_ENABLED === "true";

// eslint-disable-next-line react-refresh/only-export-components -- null is the disabled-build state
export const AssistantEntry: LazyExoticComponent<ComponentType> | null = enabled
  ? lazy(() => import("./AssistantRoot"))
  : null;

/**
 * `AssistantUIProvider` is imported statically (not via `import()`) on
 * purpose: App.tsx needs it synchronously, with no Suspense boundary, to
 * wrap the whole routed tree. When `enabled` is false the ternary below
 * collapses to the passthrough at build time, the reference to
 * `AssistantUIProvider` becomes dead, and Rollup drops it -- safe because
 * contexts/AssistantUIContext.tsx has no module-level side effects beyond
 * `createContext()` itself (no i18n, no fetch, no global registration), so
 * nothing forces the import to survive for a side effect it doesn't have.
 */
export const AssistantProvider: ComponentType<{ children: ReactNode }> = enabled
  ? AssistantUIProvider
  : ({ children }) => <>{children}</>;

const LazyHeaderTrigger: LazyExoticComponent<ComponentType> | null = enabled
  ? lazy(() => import("./triggers").then((m) => ({ default: m.HeaderTrigger })))
  : null;

/**
 * What Navbar.tsx renders in place of a header button. Navbar itself never
 * imports useAssistantUI, useTranslation("assistant") or an icon for this
 * feature -- every one of those, and the button markup, lives in the lazy
 * chunk this loads, so a build without the flag carries none of it, not even
 * the assistant.json key names.
 */
export function AssistantHeaderSlot() {
  if (!LazyHeaderTrigger) return null;
  return (
    <ErrorBoundary fallback={null}>
      <Suspense fallback={null}>
        <LazyHeaderTrigger />
      </Suspense>
    </ErrorBoundary>
  );
}

const LazyResultTrigger: LazyExoticComponent<ComponentType<{ projectId: string }>> | null = enabled
  ? lazy(() => import("./triggers").then((m) => ({ default: m.ResultTrigger })))
  : null;

export interface AssistantResultSlotProps {
  readonly projectId: string;
}

/** Same reasoning as AssistantHeaderSlot, for ResultsSection.tsx. */
export function AssistantResultSlot({ projectId }: AssistantResultSlotProps) {
  if (!LazyResultTrigger) return null;
  return (
    <ErrorBoundary fallback={null}>
      <Suspense fallback={null}>
        <LazyResultTrigger projectId={projectId} />
      </Suspense>
    </ErrorBoundary>
  );
}

const LazyProfileCard: LazyExoticComponent<ComponentType> | null = enabled
  ? lazy(() => import("./AssistantPrivacyCard").then((m) => ({ default: m.AssistantPrivacyCard })))
  : null;

/** Same reasoning as AssistantHeaderSlot, for Profile.tsx: the privacy card and its copy. */
export function AssistantProfileSlot() {
  if (!LazyProfileCard) return null;
  return (
    <ErrorBoundary fallback={null}>
      <Suspense fallback={null}>
        <LazyProfileCard />
      </Suspense>
    </ErrorBoundary>
  );
}

/** The module behind the documentation section and the guide's other parts, as the hook below hands it out. */
export type AssistantGuideModule = typeof import("./AssistantGuide");

let guideLoaded: AssistantGuideModule | null = null;
let guideLoad: Promise<AssistantGuideModule> | null = null;

function loadGuide(): Promise<AssistantGuideModule> {
  guideLoad ??= import("./AssistantGuide").then(
    (loaded) => {
      guideLoaded = loaded;
      return loaded;
    },
    (error: unknown) => {
      // A stale hashed chunk after a deploy lands here. Forgetting the promise lets
      // the next mount retry; callers that share this attempt see one report.
      guideLoad = null;
      logger.error("Assistant guide failed to load", {
        error: error instanceof Error ? error.message : String(error),
      });
      Sentry.captureException(error);
      throw error;
    },
  );
  return guideLoad;
}

function useGuide(): AssistantGuideModule | null {
  // Seeded from the module that already resolved, so a revisit paints the full page at once.
  const [guide, setGuide] = useState<AssistantGuideModule | null>(guideLoaded);

  useEffect(() => {
    let active = true;
    loadGuide().then(
      (loaded) => {
        if (active) setGuide(loaded);
      },
      () => {
        // Already reported by loadGuide. The guide simply stays absent, so a
        // page that waits on it never shows half of it.
      },
    );
    return () => {
      active = false;
    };
  }, []);

  return guide;
}

/**
 * The assistant's guide copy and its components, loaded from their own chunk,
 * or `null` while that loads, if it fails, and always in a build without the
 * flag. A caller adds everything the guide contributes to its page (a
 * table-of-contents entry, a section, a tour step) only when this is not
 * `null`, so the page never shows a part whose other half is missing. Chosen at
 * module load like everything above: a build without the flag gets a constant
 * `null` and the `import()` is dropped.
 */
// eslint-disable-next-line react-refresh/only-export-components -- a hook gated by the same build flag as the exports above
export const useAssistantGuide: () => AssistantGuideModule | null = enabled ? useGuide : () => null;

function useProjectScope(projectId: string | undefined): void {
  const { setPageProjectId } = useAssistantUI();

  useEffect(() => {
    setPageProjectId(projectId ?? null);
    return () => setPageProjectId(null);
  }, [projectId, setPageProjectId]);
}

/**
 * Tells the panel which project the current page shows, so the header button
 * opens it scoped to that project. Chosen at module load like everything above:
 * a build without the flag gets a no-op and the hook body is dropped.
 */
// eslint-disable-next-line react-refresh/only-export-components -- a hook gated by the same build flag as the exports above
export const useAssistantProjectScope: (projectId: string | undefined) => void = enabled
  ? useProjectScope
  : () => {};
