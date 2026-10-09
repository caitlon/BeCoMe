import { Children, Fragment, createElement, useMemo, type HTMLAttributes, type ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { sourceAnchorId } from "./message-shape";

// No a, img, table, heading, blockquote or pre: with `unwrapDisallowed` the text
// of a dropped element still shows, so a link or a heading comes out as plain
// text and nothing in an answer can point the browser at another address.
const ALLOWED_ELEMENTS = ["p", "strong", "em", "ul", "ol", "li", "code", "br"];
const CITATION = /\[([1-9]\d*)\]/g;
const CITE_CLASS =
  "mx-0.5 rounded border px-1 align-[1px] text-[11px] font-semibold text-muted-foreground no-underline";

type CitingTag = "p" | "li" | "strong" | "em";
const CITING_TAGS: readonly CitingTag[] = ["p", "li", "strong", "em"];

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
export function AssistantMarkdown({
  content,
  messageId,
  sourceNumbers = [],
  onCite,
}: AssistantMarkdownProps) {
  const { t } = useTranslation("assistant");

  const components = useMemo(() => {
    const known = new Set(sourceNumbers);

    function renderCitation(n: number): ReactNode {
      if (!known.has(n)) {
        return (
          <s className={cn(CITE_CLASS, "opacity-60")} title={t("message.noSuchSource")}>
            <span>[{n}]</span>
            <span className="sr-only"> ({t("message.noSuchSource")})</span>
          </s>
        );
      }
      return (
        <a
          href={`#${sourceAnchorId(messageId, n)}`}
          className={cn(CITE_CLASS, "cursor-pointer")}
          onClick={(event) => {
            event.preventDefault();
            onCite?.(n);
          }}
        >
          [{n}]
        </a>
      );
    }

    function withCitations(children: ReactNode): ReactNode {
      return Children.map(children, (child, childIndex) => {
        if (typeof child !== "string") return child;
        const parts = child.split(CITATION);
        // split with one capture group alternates text and the captured number.
        return (
          <Fragment key={childIndex}>
            {parts.map((part, partIndex) => (
              <Fragment key={partIndex}>{partIndex % 2 === 1 ? renderCitation(Number(part)) : part}</Fragment>
            ))}
          </Fragment>
        );
      });
    }

    const citing = (Tag: CitingTag) =>
      // react-markdown v10 passes the hast `node` to every override; it is dropped
      // here so it never reaches the DOM element as an unknown attribute.
      function Citing({ node: _node, children, ...props }: HTMLAttributes<HTMLElement> & { node?: unknown }) {
        return createElement(Tag, props, withCitations(children));
      };

    return Object.fromEntries(CITING_TAGS.map((tag) => [tag, citing(tag)])) as Components;
  }, [sourceNumbers, messageId, onCite, t]);

  return (
    <Markdown allowedElements={ALLOWED_ELEMENTS} unwrapDisallowed skipHtml components={components}>
      {content}
    </Markdown>
  );
}
