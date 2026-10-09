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
 * Renders one assistant answer from an allowlist of elements. `skipHtml` drops raw
 * HTML (react-markdown never parses it into elements without rehype-raw, which is
 * deliberately absent). A `[n]` marker in the text of a paragraph, list item,
 * bold or italic run becomes our own element, never a markdown link.
 */
export function AssistantMarkdown({ content, messageId, sourceNumbers, onCite }: AssistantMarkdownProps) {
  const known = useMemo(() => (sourceNumbers ? new Set(sourceNumbers) : undefined), [sourceNumbers]);
  const citation = useMemo(() => ({ known, messageId, onCite }), [known, messageId, onCite]);

  return (
    <CitationContext value={citation}>
      <Markdown allowedElements={ALLOWED_ELEMENTS} unwrapDisallowed skipHtml components={COMPONENTS}>
        {content}
      </Markdown>
    </CitationContext>
  );
}
