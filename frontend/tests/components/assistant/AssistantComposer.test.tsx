import { describe, it, expect, vi, afterEach } from 'vitest';
import { createRef } from 'react';
import { fireEvent, render, screen } from '@tests/utils';
import userEvent from '@testing-library/user-event';
import i18n from '@/i18n';
import { AssistantComposer, MAX_QUESTION_LENGTH } from '@/components/assistant/AssistantComposer';
import '@/components/assistant/i18n';

function setup(overrides: Partial<React.ComponentProps<typeof AssistantComposer>> = {}) {
  const props = {
    value: '',
    onChange: vi.fn(),
    onSend: vi.fn(),
    onCancel: vi.fn(),
    isPending: false,
    ...overrides,
  };
  render(<AssistantComposer {...props} />);
  return props;
}

const box = () => screen.getByRole('textbox', { name: 'Ask a question…' });

describe('AssistantComposer', () => {
  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  describe('keyboard', () => {
    it('sends on Enter', async () => {
      const props = setup({ value: 'hello' });

      await userEvent.type(box(), '{Enter}');

      expect(props.onSend).toHaveBeenCalledTimes(1);
    });

    it('keeps Shift+Enter as a newline and does not send', async () => {
      const props = setup({ value: 'hello' });
      box().focus();

      await userEvent.keyboard('{Shift>}{Enter}{/Shift}');

      expect(props.onSend).not.toHaveBeenCalled();
      expect(props.onChange).toHaveBeenCalledWith('hello\n');
    });

    it('does nothing for an Enter that confirms an IME candidate', () => {
      const props = setup({ value: 'hello' });

      const notPrevented = fireEvent.keyDown(box(), { key: 'Enter', isComposing: true });

      expect(notPrevented).toBe(true);
      expect(props.onSend).not.toHaveBeenCalled();
    });

    it('does not send an empty or whitespace-only draft on Enter, and adds no newline', () => {
      const props = setup({ value: '  \n ' });

      const notPrevented = fireEvent.keyDown(box(), { key: 'Enter' });

      expect(props.onSend).not.toHaveBeenCalled();
      expect(notPrevented).toBe(false);
    });

    it('does not send on Enter while a turn is pending', () => {
      const props = setup({ value: 'next question', isPending: true });

      fireEvent.keyDown(box(), { key: 'Enter' });

      expect(props.onSend).not.toHaveBeenCalled();
    });

    it('ignores other keys', async () => {
      const props = setup({ value: 'hello' });

      await userEvent.type(box(), 'a');

      expect(props.onSend).not.toHaveBeenCalled();
    });
  });

  describe('send button', () => {
    it.each([['empty', ''], ['whitespace-only', '   \n']])('is disabled for an %s draft', (_name, value) => {
      setup({ value });

      expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    });

    it('sends the draft on click', async () => {
      const props = setup({ value: 'hello' });

      await userEvent.click(screen.getByRole('button', { name: 'Send' }));

      expect(props.onSend).toHaveBeenCalledTimes(1);
    });
  });

  describe('while a turn is pending', () => {
    it('shows Stop in place of Send, and Stop cancels', async () => {
      const props = setup({ value: '', isPending: true });

      expect(screen.queryByRole('button', { name: 'Send' })).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Stop' }));

      expect(props.onCancel).toHaveBeenCalledTimes(1);
      expect(props.onSend).not.toHaveBeenCalled();
    });

    it('keeps the box enabled so the next question can be typed', async () => {
      const props = setup({ isPending: true });

      expect(box()).toBeEnabled();
      await userEvent.type(box(), 'x');

      expect(props.onChange).toHaveBeenCalledWith('x');
    });
  });

  describe('box', () => {
    it('limits the draft to the length the API accepts', () => {
      setup();

      expect(MAX_QUESTION_LENGTH).toBe(4000);
      expect(box()).toHaveAttribute('maxlength', '4000');
    });

    it('counts the characters against the limit', () => {
      setup({ value: 'hello' });

      expect(screen.getByText('5 / 4000')).toBeInTheDocument();
    });

    it('shows the keyboard hint', () => {
      setup();

      expect(screen.getByText('Enter to send · Shift+Enter for a new line')).toBeInTheDocument();
    });

    it('hands its element to the ref it is given', () => {
      const textareaRef = createRef<HTMLTextAreaElement>();
      setup({ textareaRef });

      expect(textareaRef.current).toBe(box());
    });

    it('speaks Czech when the language is Czech', async () => {
      await i18n.changeLanguage('cs');
      setup({ isPending: true });

      expect(screen.getByRole('textbox', { name: 'Napište otázku…' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Zastavit' })).toBeInTheDocument();
    });
  });
});
