import i18n from "@/i18n";
import enAssistant from "@/i18n/locales/en/assistant.json";
import csAssistant from "@/i18n/locales/cs/assistant.json";

/**
 * Registers the assistant namespace at runtime, outside the static `resources`
 * map in i18n/index.ts, so a build without the feature carries none of its
 * copy. Both of the feature's lazy chunks (AssistantRoot.tsx for the panel,
 * triggers.tsx for the buttons) import this module; in a build they share one
 * i18n chunk that is evaluated once. The `hasResourceBundle` guards matter for
 * tests, which import the module repeatedly, and for dev HMR, where re-running
 * the module would otherwise replace the bundles and leave an edited
 * assistant.json unapplied until a full reload.
 */
export function registerAssistantI18n(): void {
  if (!i18n.hasResourceBundle("en", "assistant")) {
    i18n.addResourceBundle("en", "assistant", enAssistant);
  }
  if (!i18n.hasResourceBundle("cs", "assistant")) {
    i18n.addResourceBundle("cs", "assistant", csAssistant);
  }
}

registerAssistantI18n();
