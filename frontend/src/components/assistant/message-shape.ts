import type { AnswerChecks, SourceRef } from "@/types/api";

/** The id of a source row, which a `[n]` citation in the same message points at. */
export function sourceAnchorId(messageId: string, n: number): string {
  return `assistant-src-${messageId}-${n}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toSource(value: unknown): SourceRef | null {
  if (!isRecord(value)) return null;
  const { n, title, section, snippet, url, layer } = value;
  if (typeof n !== "number" || !Number.isSafeInteger(n) || n < 1) return null;
  if (typeof title !== "string" || typeof section !== "string") return null;
  if (layer !== "public" && layer !== "local") return null;
  if (url !== null && typeof url !== "string") return null;
  // A stored entry from before snippets existed has none; it shows an empty quote.
  return { n, title, section, snippet: typeof snippet === "string" ? snippet : "", url, layer };
}

/**
 * Storage only checks that `sources` is an array and a stored message can be edited
 * by hand, so each entry is checked here: malformed ones and repeated numbers drop out.
 */
export function cleanSources(value: unknown): SourceRef[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<number>();
  const sources: SourceRef[] = [];
  for (const entry of value) {
    const source = toSource(entry);
    if (source && !seen.has(source.n)) {
      seen.add(source.n);
      sources.push(source);
    }
  }
  return sources;
}

export function cleanToolsUsed(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((tool): tool is string => typeof tool === "string") : [];
}

/** Only a complete set of checks counts; anything else is treated as "no checks". */
export function cleanChecks(value: unknown): AnswerChecks | null {
  if (!isRecord(value)) return null;
  const { citations_valid, numbers_grounded, ungrounded_numbers } = value;
  if (typeof citations_valid !== "boolean" || typeof numbers_grounded !== "boolean") return null;
  if (!Array.isArray(ungrounded_numbers)) return null;
  return {
    citations_valid,
    numbers_grounded,
    ungrounded_numbers: ungrounded_numbers.filter((n): n is string => typeof n === "string"),
  };
}
