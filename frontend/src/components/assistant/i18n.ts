import i18n from "@/i18n";
import enAssistant from "@/i18n/locales/en/assistant.json";
import csAssistant from "@/i18n/locales/cs/assistant.json";

/**
 * Registers the assistant namespace at runtime, outside the static `resources`
 * map in i18n/index.ts, so a build without the feature carries none of its
 * copy. Both of the feature's lazy chunks import this module (AssistantRoot.tsx
 * for the panel, triggers.tsx for the buttons) because either can load first.
 * Idempotent: whichever import runs second finds the bundles already there.
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
