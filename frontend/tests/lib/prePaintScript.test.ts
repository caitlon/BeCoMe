import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// The inline script in index.html runs before the bundle, so it cannot be imported.
// Read it out of the page and run it against stubbed browser state.
let script: string;

beforeAll(() => {
  const html = readFileSync(resolve(__dirname, "../../index.html"), "utf-8");
  const inline = [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)];
  expect(inline).toHaveLength(1);
  script = inline[0][1];
});

interface Browser {
  readonly theme?: string | null;
  readonly language?: string | null;
  readonly darkOs?: boolean;
  readonly navigatorLanguages?: readonly string[];
  readonly navigatorLanguage?: string;
  readonly noLanguagesList?: boolean;
  readonly noMatchMedia?: boolean;
  readonly storageThrows?: boolean;
}

function run({
  theme = null,
  language = null,
  darkOs = false,
  navigatorLanguages = ["en-US"],
  navigatorLanguage = navigatorLanguages[0],
  noLanguagesList = false,
  noMatchMedia = false,
  storageThrows = false,
}: Browser): string[] {
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => {
      if (storageThrows) throw new DOMException("denied", "SecurityError");
      if (key === "become-theme") return theme;
      if (key === "become-language") return language;
      return null;
    },
  });
  vi.stubGlobal(
    "matchMedia",
    noMatchMedia
      ? undefined
      : (query: string) => ({ matches: query === "(prefers-color-scheme: dark)" && darkOs }),
  );
  vi.stubGlobal("navigator", {
    languages: noLanguagesList ? undefined : navigatorLanguages,
    language: navigatorLanguage,
  });

  new Function(script)();

  return [...document.documentElement.classList];
}

describe("pre-paint script in index.html", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.className = "";
  });

  it("uses a stored dark theme", () => {
    expect(run({ theme: "dark" })).toContain("dark");
  });

  it("prefers a stored light theme over a dark OS", () => {
    const classes = run({ theme: "light", darkOs: true });

    expect(classes).toContain("light");
    expect(classes).not.toContain("dark");
  });

  it("follows a dark OS when nothing is stored", () => {
    expect(run({ darkOs: true })).toContain("dark");
  });

  it("follows a light OS when the stored choice is system", () => {
    expect(run({ theme: "system", darkOs: false })).toContain("light");
  });

  it("treats an unknown stored theme as system", () => {
    expect(run({ theme: "purple", darkOs: true })).toContain("dark");
  });

  it("falls back to light when matchMedia is missing and nothing is stored", () => {
    const classes = run({ noMatchMedia: true });

    expect(classes).toContain("light");
    expect(classes).not.toContain("dark");
  });

  it("marks a stored regional Czech language as pending", () => {
    expect(run({ language: "cs-CZ" })).toContain("lang-pending");
  });

  it("does not mark stored regional English even when the browser prefers Czech", () => {
    expect(run({ language: "en-US", navigatorLanguages: ["cs"] })).not.toContain("lang-pending");
  });

  it("falls back to navigator.language when navigator.languages is missing", () => {
    const classes = run({ noLanguagesList: true, navigatorLanguage: "cs-CZ" });

    expect(classes).toContain("lang-pending");
  });

  it("marks a stored Czech language as pending", () => {
    expect(run({ language: "cs" })).toContain("lang-pending");
  });

  it("does not mark stored English even when the browser reports Czech", () => {
    expect(run({ language: "en", navigatorLanguages: ["cs-CZ"] })).not.toContain("lang-pending");
  });

  it("takes the first supported browser language, skipping unsupported ones", () => {
    expect(run({ navigatorLanguages: ["de-DE", "cs-CZ", "en"] })).toContain("lang-pending");
  });

  it("does not mark a browser list that reaches English first", () => {
    expect(run({ navigatorLanguages: ["en-US", "cs"] })).not.toContain("lang-pending");
  });

  it("does not mark a browser with no supported language", () => {
    expect(run({ navigatorLanguages: ["de-DE"] })).not.toContain("lang-pending");
  });

  it("still sets a theme and a language when storage throws", () => {
    const classes = run({ storageThrows: true, darkOs: true, navigatorLanguages: ["cs"] });

    expect(classes).toContain("dark");
    expect(classes).toContain("lang-pending");
  });
});
