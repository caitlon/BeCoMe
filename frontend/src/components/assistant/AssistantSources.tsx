import { useTranslation } from "react-i18next";
import type { SourceRef } from "@/types/api";
import { sourceAnchorId } from "./message-shape";
import { isAllowedAssistantUrl } from "./url-allowlist";

interface SourceRowProps {
  readonly messageId: string;
  readonly source: SourceRef;
  readonly open: boolean;
  readonly onToggle: (n: number) => void;
}

function SourceRow({ messageId, source, open, onToggle }: SourceRowProps) {
  const { t } = useTranslation("assistant");
  const rowId = sourceAnchorId(messageId, source.n);
  const detailId = `${rowId}-detail`;
  const isLocal = source.layer === "local";
  // A local source never links, whatever its url says.
  const href = !isLocal && isAllowedAssistantUrl(source.url) ? source.url : null;

  return (
    <div id={rowId} className="py-0.5">
      <div className="flex items-baseline gap-2">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={detailId}
          onClick={() => onToggle(source.n)}
          className="flex min-w-0 flex-1 items-baseline gap-2 rounded text-left"
        >
          <span className="min-w-[18px] text-[11px] font-semibold">[{source.n}]</span>
          <span className="min-w-0">
            <span className="underline decoration-muted-foreground underline-offset-2">{source.title}</span>
            <span> · {source.section}</span>
          </span>
        </button>
        {isLocal && (
          <span
            title={t("message.localHint")}
            className="whitespace-nowrap rounded border px-1.5 text-[10.5px]"
          >
            {t("message.localCopy")}
          </span>
        )}
      </div>
      {open && (
        <div id={detailId} className="mt-1 space-y-1 rounded-md border bg-card p-2 text-foreground">
          {source.snippet !== "" && (
            <p className="italic text-muted-foreground">
              <q>{source.snippet}</q>
            </p>
          )}
          {isLocal ? <p>{t("message.localHint")}</p> : <p>{t("message.publicLayer")}</p>}
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              {t("message.openSource")}
            </a>
          )}
        </div>
      )}
    </div>
  );
}

export interface AssistantSourcesProps {
  readonly messageId: string;
  readonly sources: readonly SourceRef[];
  readonly openN: number | null;
  readonly onToggle: (n: number) => void;
}

/** Compact source rows; one row at a time shows its quote and, for a public page, a link. */
export function AssistantSources({ messageId, sources, openN, onToggle }: AssistantSourcesProps) {
  const { t } = useTranslation("assistant");

  return (
    <div className="mt-2.5 border-t pt-2 text-[12.5px] text-muted-foreground">
      <p className="mb-1.5 text-[11px] uppercase tracking-wide">{t("message.sources")}</p>
      {sources.map((source) => (
        <SourceRow
          key={source.n}
          messageId={messageId}
          source={source}
          open={openN === source.n}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}
