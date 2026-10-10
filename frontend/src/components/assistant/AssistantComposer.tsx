import { useImperativeHandle, useLayoutEffect, useRef, type KeyboardEvent, type Ref } from "react";
import { useTranslation } from "react-i18next";
import { Send, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

/** Mirrors AssistantChatRequest.message (api/schemas/assistant.py). */
export const MAX_QUESTION_LENGTH = 4000;

// What a keydown reports while an input method is handling the key.
const IME_KEY_CODE = 229;

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
 * confirms an IME candidate does neither: Safari reports that one after the
 * composition has ended, with `isComposing` already false, but with keyCode 229.
 * The box is never disabled, because the hook puts a refused question back into
 * it while the user may be typing. It grows with its text, and scrolls past six lines.
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
  const innerRef = useRef<HTMLTextAreaElement>(null);
  // The element is the handle: the parent focuses it, this component measures it.
  useImperativeHandle(textareaRef, () => innerRef.current as HTMLTextAreaElement, []);

  // After every change of the text, however it came (typing, a suggestion, a restored question).
  useLayoutEffect(() => {
    const element = innerRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${element.scrollHeight}px`;
  }, [value]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || event.keyCode === IME_KEY_CODE) {
      return;
    }
    event.preventDefault();
    if (canSend) onSend();
  }

  return (
    <div className="border-t px-4 pb-3 pt-2.5">
      <div className="flex items-end gap-2">
        <Textarea
          ref={innerRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_QUESTION_LENGTH}
          rows={1}
          placeholder={t("composer.placeholder")}
          aria-label={t("composer.placeholder")}
          className="max-h-[8.5rem] min-h-11 resize-none overflow-y-auto"
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
