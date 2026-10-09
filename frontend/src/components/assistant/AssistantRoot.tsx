/**
 * Placeholder so `vite build` can resolve the dynamic import in
 * components/assistant/index.tsx from the very first commit of the gate --
 * module resolution happens before dead-code elimination proves the branch
 * referencing this file unreachable, so the file must exist on disk in both
 * build states. A later change replaces this body with the real panel wiring.
 */
export default function AssistantRoot() {
  return null;
}
