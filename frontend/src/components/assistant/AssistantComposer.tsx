import type { KeyboardEvent, Ref } from "react";
import { useTranslation } from "react-i18next";
import { Send, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

/** Mirrors AssistantChatRequest.message (api/schemas/assistant.py). */
export const MAX_QUESTION_LENGTH = 4000;

export interface AssistantComposerProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly onSend: () => void;
  readonly onCancel: () => void;
  /** A turn is in flight: the button becomes Stop, the box stays open for the next question. */
  readonly isPending: boolean;
  readonly textareaRef?: Ref<HTMLTextAreaElement>;
}

/**
 * The question box. Enter sends, Shift+Enter breaks the line, and an Enter that
 * confirms an IME candidate does neither. The box is never disabled, because the
 * hook puts a refused question back into it while the user may be typing.
 */
export function AssistantComposer({
  value,
  onChange,
  onSend,
  onCancel,
  isPending,
  textareaRef,
}: AssistantComposerProps) {
  const { t } = useTranslation("assistant");
  const { t: tCommon } = useTranslation("common");
  const canSend = value.trim() !== "" && !isPending;

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (canSend) onSend();
  }

  return (
    <div className="border-t px-4 pb-3 pt-2.5">
      <div className="flex items-end gap-2">
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_QUESTION_LENGTH}
          rows={1}
          placeholder={t("composer.placeholder")}
          aria-label={t("composer.placeholder")}
          className="min-h-11 resize-none"
        />
        {isPending ? (
          <Button
            type="button"
            size="icon"
            variant="outline"
            onClick={onCancel}
            aria-label={t("composer.stop")}
            title={t("composer.stop")}
          >
            <Square className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            disabled={!canSend}
            onClick={onSend}
            aria-label={tCommon("send")}
            title={tCommon("send")}
          >
            <Send className="h-4 w-4" />
          </Button>
        )}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
        <span>{t("composer.hint")}</span>
        <span className="font-mono">
          {value.length} / {MAX_QUESTION_LENGTH}
        </span>
      </div>
    </div>
  );
}
