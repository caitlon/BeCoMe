import { lazy, Suspense, type ComponentType, type LazyExoticComponent, type ReactNode } from "react";
import { AssistantUIProvider } from "@/contexts/AssistantUIContext";

/**
 * Build-time kill switch for the whole local assistant feature (BCM-120),
 * computed once so every export below shares the same answer. Vite
 * statically replaces `import.meta.env.VITE_ASSISTANT_ENABLED` with a
 * literal at build time, so when it is not exactly "true" every branch below
 * is unreachable and `vite build`'s dead-code elimination drops the dynamic
 * `import()` calls together with it -- neither the AssistantRoot chunk nor
 * the triggers chunk (buttons, assistant.json content, every
 * /api/v1/assistant/* path) reaches `dist/`. That only holds for
 * `vite build`; `vite dev` serves unbundled ESM and never tree-shakes (see
 * this task's Step 5 and the closing task, Task 128.13, for the real
 * build+grep verification).
 *
 * The variable itself lives only in a developer's own
 * frontend/.env.development.local (gitignored via the repo's `*.local`
 * pattern); docker/Dockerfile, frontend/Dockerfile and every Railway service
 * never set it, so every deployed build takes the disabled branch below.
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
    <Suspense fallback={null}>
      <LazyHeaderTrigger />
    </Suspense>
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
    <Suspense fallback={null}>
      <LazyResultTrigger projectId={projectId} />
    </Suspense>
  );
}
