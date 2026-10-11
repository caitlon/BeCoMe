import {
  Children,
  Fragment,
  createContext,
  createElement,
  useContext,
  useMemo,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import Markdown, { type Components } from "react-markdown";
import { useTranslation } from "react-i18next";
import { sourceAnchorId } from "./message-shape";

// No a, img, table, heading, blockquote or pre: with `unwrapDisallowed` the text
// of a dropped element still shows, so a link or a heading comes out as plain
// text and nothing in an answer can point the browser at another address.
const ALLOWED_ELEMENTS = ["p", "strong", "em", "ul", "ol", "li", "code", "br"];
const CITATION = /\[([1-9]\d*)\]/g;
// The start of a reference-style definition ("[1]: url") at the head of a line, behind any
// quote or list markers; markdown trims spaces inside the label. Markdown would swallow the
// definition and turn every "[1]" in the answer into a link reference, which loses the brackets.
const DEFINITION_START = /^((?:[ \t]*(?:>|[-*+]|\d+[.)]))*[ \t]*)\[(?=[ \t]*[1-9]\d*[ \t]*\]:)/;
const FENCE = /^ {0,3}(`{3,}|~{3,})/;
// Any line with four leading spaces or a tab is taken for code, a list continuation included.
const INDENTED_CODE = /^(?: {4}|\t)/;
const CITE_BASE = "mx-0.5 rounded border px-1 align-[1px] text-[11px] font-semibold text-muted-foreground";
const CITE_CLASS = `${CITE_BASE} no-underline cursor-pointer`;
// Its own list: `no-underline` would beat the line-through the <s> brings along.
const UNKNOWN_CITE_CLASS = `${CITE_BASE} line-through opacity-60`;

interface CitationContextValue {
  /** Undefined while the sources are not known: the marker stays plain text. */
  readonly known?: ReadonlySet<number>;
  readonly messageId: string;
  readonly onCite?: (n: number) => void;
}

const CitationContext = createContext<CitationContextValue>({ messageId: "" });

function Citation({ digits }: { readonly digits: string }) {
  const { t } = useTranslation("assistant");
  const { known, messageId, onCite } = useContext(CitationContext);
  const n = Number(digits);

  if (!known) return <>[{digits}]</>;
  if (!Number.isSafeInteger(n) || !known.has(n)) {
    return (
      <s className={UNKNOWN_CITE_CLASS}>
        <span>[{digits}]</span>
        <span className="sr-only"> ({t("message.noSuchSource")})</span>
      </s>
    );
  }
  return (
    <a
      href={`#${sourceAnchorId(messageId, n)}`}
      className={CITE_CLASS}
      onClick={(event) => {
        event.preventDefault();
        onCite?.(n);
      }}
    >
      [{digits}]
    </a>
  );
}

function withCitations(children: ReactNode): ReactNode {
  // Children.map keys the elements the callback returns by position itself.
  return Children.map(children, (child) => {
    if (typeof child !== "string") return child;
    const pieces: ReactNode[] = [];
    let end = 0;
    for (const match of child.matchAll(CITATION)) {
      if (match.index > end) pieces.push(<Fragment key={`t${end}`}>{child.slice(end, match.index)}</Fragment>);
      pieces.push(<Citation key={`c${match.index}`} digits={match[1]} />);
      end = match.index + match[0].length;
    }
    if (end < child.length) pieces.push(<Fragment key={`t${end}`}>{child.slice(end)}</Fragment>);
    return <Fragment>{pieces}</Fragment>;
  });
}

// Escaping the opening bracket makes the line plain text, so no definition exists and
// the "[n]" in it is a citation like any other. Code is left as written.
function neutraliseDefinitions(content: string): string {
  let fence: string | undefined;
  return content
    .split("\n")
    .map((line) => {
      const run = FENCE.exec(line)?.[1];
      if (fence) {
        if (line.trim() === run && run.length >= fence.length && run[0] === fence[0]) fence = undefined;
        return line;
      }
      if (run) fence = run;
      return run || INDENTED_CODE.test(line) ? line : line.replace(DEFINITION_START, "$1\\[");
    })
    .join("\n");
}

type CitingTag = "p" | "li" | "strong" | "em";

// Built once at module level: an override whose identity changes between renders
// makes React remount every element it renders, which drops the focus of a
// clicked citation and would rebuild a streamed answer on every token.
const citing = (Tag: CitingTag) =>
  // react-markdown v10 passes the hast `node` to every override; it is dropped
  // here so it never reaches the DOM element as an unknown attribute.
  function Citing({ node: _node, children, ...props }: HTMLAttributes<HTMLElement> & { node?: unknown }) {
    return createElement(Tag, props, withCitations(children));
  };

const COMPONENTS: Components = { p: citing("p"), li: citing("li"), strong: citing("strong"), em: citing("em") };

export interface AssistantMarkdownProps {
  readonly content: string;
  readonly messageId: string;
  /**
   * Numbers of the sources this answer really has; any other [n] is struck through.
   * Undefined means the sources are not known yet, and every [n] stays plain text.
   */
  readonly sourceNumbers?: readonly number[];
  readonly onCite?: (n: number) => void;
}

/**
 * Renders one assistant answer from an allowlist of elements. Raw HTML is shown as
 * text: react-markdown never parses it into elements without rehype-raw, which is
 * deliberately absent. A `[n]` marker in the text of a paragraph, list item, bold or
 * italic run becomes our own element: an in-page anchor when the sources are known and
 * include n, a struck-through marker when they do not, plain text while they are unknown.
 * A "[n]: url" line is shown as text, so it cannot turn the markers into markdown links.
 */
export function AssistantMarkdown({ content, messageId, sourceNumbers, onCite }: AssistantMarkdownProps) {
  const known = useMemo(() => (sourceNumbers ? new Set(sourceNumbers) : undefined), [sourceNumbers]);
  const citation = useMemo(() => ({ known, messageId, onCite }), [known, messageId, onCite]);
  const text = useMemo(() => neutraliseDefinitions(content), [content]);

  return (
    <CitationContext value={citation}>
      {/* No rehype-raw here, so raw HTML stays text; adding one needs skipHtml back or a sanitizer. */}
      <Markdown allowedElements={ALLOWED_ELEMENTS} unwrapDisallowed components={COMPONENTS}>
        {text}
      </Markdown>
    </CitationContext>
  );
}
