/** The id of a source row, which a `[n]` citation in the same message points at. */
export function sourceAnchorId(messageId: string, n: number): string {
  return `assistant-src-${messageId}-${n}`;
}
