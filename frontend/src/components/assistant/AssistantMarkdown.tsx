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
  readonly known: ReadonlySet<number>;
  readonly messageId: string;
  readonly onCite?: (n: number) => void;
}

const CitationContext = createContext<CitationContextValue>({ known: new Set(), messageId: "" });

function Citation({ digits }: { readonly digits: string }) {
  const { t } = useTranslation("assistant");
  const { known, messageId, onCite } = useContext(CitationContext);
  const n = Number(digits);

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
  return Children.map(children, (child, childIndex) => {
    if (typeof child !== "string") return child;
    const parts = child.split(CITATION);
    // split with one capture group alternates text and the captured digits.
    return (
      <Fragment key={childIndex}>
        {parts.map((part, partIndex) => (
          <Fragment key={partIndex}>{partIndex % 2 === 1 ? <Citation digits={part} /> : part}</Fragment>
        ))}
      </Fragment>
    );
  });
}

type CitingTag = "p" | "li" | "strong" | "em";
const CITING_TAGS: readonly CitingTag[] = ["p", "li", "strong", "em"];

// Built once at module level: an override whose identity changes between renders
// makes React remount every element it renders, which drops the focus of a
// clicked citation and would rebuild a streamed answer on every token.
const citing = (Tag: CitingTag) =>
  // react-markdown v10 passes the hast `node` to every override; it is dropped
  // here so it never reaches the DOM element as an unknown attribute.
  function Citing({ node: _node, children, ...props }: HTMLAttributes<HTMLElement> & { node?: unknown }) {
    return createElement(Tag, props, withCitations(children));
  };

const COMPONENTS = Object.fromEntries(CITING_TAGS.map((tag) => [tag, citing(tag)])) as Components;

export interface AssistantMarkdownProps {
  readonly content: string;
  readonly messageId: string;
  /** Numbers of the sources this answer really has; any other [n] is struck through. */
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
  const known = useMemo(() => new Set(sourceNumbers), [sourceNumbers]);
  const citation = useMemo(() => ({ known, messageId, onCite }), [known, messageId, onCite]);

  return (
    <CitationContext value={citation}>
      <Markdown allowedElements={ALLOWED_ELEMENTS} unwrapDisallowed skipHtml components={COMPONENTS}>
        {content}
      </Markdown>
    </CitationContext>
  );
}
