import { describe, it, expect, vi, afterEach } from 'vitest';
import { act, fireEvent, render, screen, within } from '@tests/utils';
import userEvent from '@testing-library/user-event';
import i18n from '@/i18n';
import { AssistantFeed, type AssistantFeedProps } from '@/components/assistant/AssistantFeed';
import type { AssistantMessage } from '@/components/assistant/useAssistantChat';
import { AssistantUIProvider, useAssistantUI } from '@/contexts/AssistantUIContext';
import '@/components/assistant/i18n';

// Counts how often a message body is rendered, standing in for the markdown reparse.
const markdownRenders = vi.fn();
vi.mock('@/components/assistant/AssistantMarkdown', () => ({
  AssistantMarkdown: ({ content }: { content: string }) => {
    markdownRenders(content);
    return <p>{content}</p>;
  },
}));

let counter = 0;
function msg(role: 'user' | 'assistant', content: string, extra: Partial<AssistantMessage> = {}): AssistantMessage {
  counter += 1;
  return { id: `m${counter}`, role, content, status: 'done', createdAt: 1000, ...extra };
}
const user = (content: string, extra: Partial<AssistantMessage> = {}) => msg('user', content, extra);
const answer = (content: string, extra: Partial<AssistantMessage> = {}) => msg('assistant', content, extra);
const failure = (code: number, extra: Partial<AssistantMessage> = {}) =>
  answer('', { status: 'error', error: { code, detail: 'secret detail' }, ...extra });

function props(overrides: Partial<AssistantFeedProps> = {}): AssistantFeedProps {
  return {
    messages: [],
    historyWindowStart: -1,
    isPending: false,
    pendingSeconds: 0,
    mode: 'workflow',
    onRetry: vi.fn(),
    ...overrides,
  };
}

function renderFeed(overrides: Partial<AssistantFeedProps> = {}) {
  const feedProps = props(overrides);
  const view = render(<AssistantFeed {...feedProps} />);
  const rerender = (next: Partial<AssistantFeedProps>) =>
    view.rerender(<AssistantFeed {...feedProps} {...next} />);
  return { ...view, feedProps, rerender };
}

const log = () => screen.getByRole('log', { name: 'Conversation' });

describe('AssistantFeed', () => {
  afterEach(async () => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    markdownRenders.mockClear();
    await i18n.changeLanguage('en');
  });

  describe('log', () => {
    it('is a log named for the conversation, in the order of the messages', () => {
      renderFeed({ messages: [user('First?'), answer('First.'), user('Second?'), answer('Second.')] });

      expect(log()).toHaveTextContent(/First\?.*First\..*Second\?.*Second\./);
    });

    it('is busy while a turn runs, so tokens are not announced one by one', () => {
      const { rerender } = renderFeed({ isPending: false });
      expect(log()).toHaveAttribute('aria-busy', 'false');

      rerender({ isPending: true, messages: [user('Q'), answer('', { status: 'pending' })] });

      expect(log()).toHaveAttribute('aria-busy', 'true');
    });

    it('wraps long unbroken words instead of widening the panel', () => {
      renderFeed();

      expect(log()).toHaveClass('break-words');
    });
  });

  describe('pending answer', () => {
    const waiting = [user('Q'), answer('', { status: 'pending' })];

    it('shows the indicator and no empty bubble for an answer with no text yet', () => {
      renderFeed({ messages: waiting, isPending: true });

      expect(screen.getByText('Answering…')).toBeInTheDocument();
      expect(log().firstElementChild?.children).toHaveLength(2);
    });

    it.each([
      [0, 'Searching the documentation…'],
      [2, 'Searching the documentation…'],
      [3, 'Reading the project…'],
      [7, 'Reading the project…'],
      [8, 'Writing the answer. This can take up to a minute.'],
      [75, 'Writing the answer. This can take up to a minute.'],
    ])('names the phase by the seconds waited without a stream: %is', (seconds, label) => {
      renderFeed({ messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: seconds });

      expect(screen.getByText(label)).toBeInTheDocument();
    });

    it('shows the phase rather than a cursor when a mode that does not stream has text', () => {
      const { container } = renderFeed({
        messages: [user('Q'), answer('Some text', { status: 'pending' })],
        isPending: true,
        mode: 'hybrid',
        pendingSeconds: 1,
      });

      expect(screen.getByText('Searching the documentation…')).toBeInTheDocument();
      expect(container.querySelector('span[aria-hidden="true"].animate-pulse')).not.toBeInTheDocument();
    });

    it('treats agent mode like hybrid', () => {
      renderFeed({ messages: waiting, isPending: true, mode: 'agent', pendingSeconds: 4 });

      expect(screen.getByText('Reading the project…')).toBeInTheDocument();
    });

    it('streams the text with a cursor after it in workflow mode', () => {
      const { container } = renderFeed({
        messages: [user('Q'), answer('The best comp', { status: 'pending' })],
        isPending: true,
      });

      expect(screen.getByText('The best comp')).toBeInTheDocument();
      expect(container.querySelector('span[aria-hidden="true"].animate-pulse')).toBeInTheDocument();
      expect(screen.queryByText('Answering…')).not.toBeInTheDocument();
    });

    it('speaks Czech', async () => {
      await i18n.changeLanguage('cs');
      renderFeed({ messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: 9 });

      expect(screen.getByText('Píšu odpověď. Může to trvat až minutu.')).toBeInTheDocument();
    });
  });

  describe('history separator', () => {
    const thread = [
      user('q0'), answer('a0'), user('q1'), answer('a1'), user('q2'), answer('a2'),
    ];

    it('is drawn right before the oldest message the next request carries', () => {
      renderFeed({ messages: thread, historyWindowStart: 2 });

      const separator = screen.getByRole('separator');
      expect(separator).toHaveTextContent('Older messages are no longer sent with new questions.');
      expect(separator.nextElementSibling).toHaveTextContent('q1');
      expect(separator.previousElementSibling).toHaveTextContent('a0');
    });

    it.each([
      ['every message is still sent (-1)', -1],
      ['the window starts at the first message', 0],
    ])('is not drawn when %s', (_name, start) => {
      renderFeed({ messages: thread, historyWindowStart: start });

      expect(screen.queryByRole('separator')).not.toBeInTheDocument();
    });

    it('is not drawn when nothing answered lies before the window', () => {
      const failed = [
        user('lost', { status: 'error' }),
        failure(503),
        ...thread.slice(2),
      ];

      renderFeed({ messages: failed, historyWindowStart: 2 });

      expect(screen.queryByRole('separator')).not.toBeInTheDocument();
    });
  });

  describe('trying again', () => {
    it('offers it on the last failed answer and sends that turn question, not the draft', async () => {
      const { feedProps } = renderFeed({
        messages: [user('Older?'), answer('Older.'), user('Why only moderate?'), failure(503)],
      });

      await userEvent.click(screen.getByRole('button', { name: 'Try again' }));

      expect(feedProps.onRetry).toHaveBeenCalledTimes(1);
      expect(feedProps.onRetry).toHaveBeenCalledWith('Why only moderate?');
    });

    it('offers it on a cut answer too, below the muted partial text', async () => {
      const { feedProps } = renderFeed({
        messages: [user('Q?'), answer('Half of it', { status: 'cut' })],
      });

      await userEvent.click(screen.getByRole('button', { name: 'Try again' }));

      expect(feedProps.onRetry).toHaveBeenCalledWith('Q?');
    });

    it('offers it only on the last answer', () => {
      renderFeed({
        messages: [user('Q1'), failure(503), user('Q2'), answer('Fine.')],
      });

      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it('offers it once even when an earlier answer failed too', () => {
      renderFeed({ messages: [user('Q1'), failure(503), user('Q2'), failure(503)] });

      expect(screen.getAllByRole('button', { name: 'Try again' })).toHaveLength(1);
    });

    it('is not offered for an answer that no question precedes', () => {
      renderFeed({ messages: [answer('Fine.'), failure(503)] });

      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it('is not offered while a turn is pending', () => {
      renderFeed({
        messages: [user('Q1'), failure(503), user('Q2'), answer('', { status: 'pending' })],
        isPending: true,
      });

      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it('is not offered when the question is no longer in the list', () => {
      renderFeed({ messages: [failure(503)] });

      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it('is not offered for a cancelled answer, which is not a failure', () => {
      renderFeed({ messages: [user('Q'), answer('Part', { status: 'cancelled' })] });

      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it('never shows the server detail', () => {
      renderFeed({ messages: [user('Q'), failure(503)] });

      expect(log()).not.toHaveTextContent('secret detail');
    });

    it('gives a settled message the same retry on every render of the feed', () => {
      const messages = [user('Q?'), failure(503)];
      const onRetry = vi.fn();
      const { rerender } = renderFeed({ messages, onRetry });
      const before = screen.getByRole('button', { name: 'Try again' });

      rerender({ messages, onRetry, pendingSeconds: 5 });

      expect(screen.getByRole('button', { name: 'Try again' })).toBe(before);
    });
  });

  describe('a rate limit', () => {
    it('holds the retry back until Retry-After has passed, then brings it', () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
      vi.setSystemTime(1_000_000);
      renderFeed({
        messages: [
          user('Q?'),
          failure(429, { createdAt: 1_000_000, error: { code: 429, detail: 'x', retryAfter: 120 } }),
        ],
      });
      expect(screen.getByText('Message limit reached. Try again in 2 min.')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(119_000);
      });
      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(1_000);
      });
      expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });

    it('counts the wait from the turn, so a block restored after a reload is already open', () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
      vi.setSystemTime(1_000_000);
      renderFeed({
        messages: [
          user('Q?'),
          failure(429, { createdAt: 1_000_000 - 200_000, error: { code: 429, detail: 'x', retryAfter: 60 } }),
        ],
      });

      act(() => {
        vi.advanceTimersByTime(0);
      });

      expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });

    it('offers the retry at once when the server named no wait', () => {
      renderFeed({ messages: [user('Q?'), failure(429)] });

      expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });

    it('schedules no timer for a failure that has no wait', () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });

      renderFeed({ messages: [user('Q?'), failure(503)] });

      expect(vi.getTimerCount()).toBe(0);
    });

    it('clears its timer when the feed goes away', () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
      vi.setSystemTime(1_000_000);
      const { unmount } = renderFeed({
        messages: [
          user('Q?'),
          failure(429, { createdAt: 1_000_000, error: { code: 429, detail: 'x', retryAfter: 60 } }),
        ],
      });

      unmount();

      expect(vi.getTimerCount()).toBe(0);
    });
  });

  describe('a project that is gone (404)', () => {
    function Probe() {
      const { isOpen, projectId } = useAssistantUI();
      return <output data-testid="ui">{`${isOpen}/${projectId ?? 'general'}`}</output>;
    }

    function renderGone() {
      const feedProps = props({ messages: [user('Q?'), failure(404)] });
      function Harness() {
        const { openAssistant } = useAssistantUI();
        return (
          <>
            <button onClick={() => openAssistant('p1')}>open</button>
            <AssistantFeed {...feedProps} />
            <Probe />
          </>
        );
      }
      render(
        <AssistantUIProvider>
          <Harness />
        </AssistantUIProvider>
      );
      return feedProps;
    }

    it('offers the general thread and the project list, and no retry', () => {
      renderGone();

      expect(screen.getByRole('button', { name: 'Ask without the project' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Open projects' })).toHaveAttribute('href', '/projects');
      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it('switches the panel to the general thread', async () => {
      renderGone();
      await userEvent.click(screen.getByRole('button', { name: 'open' }));
      expect(screen.getByTestId('ui')).toHaveTextContent('true/p1');

      await userEvent.click(screen.getByRole('button', { name: 'Ask without the project' }));

      expect(screen.getByTestId('ui')).toHaveTextContent('true/general');
    });

    it('closes the panel when the user leaves for the project list', async () => {
      renderGone();
      await userEvent.click(screen.getByRole('button', { name: 'open' }));

      await userEvent.click(screen.getByRole('link', { name: 'Open projects' }));

      expect(screen.getByTestId('ui')).toHaveTextContent(/^false\//);
    });

    it('offers it only on the last answer', () => {
      renderFeed({ messages: [user('Q1?'), failure(404), user('Q2?'), failure(404)] });

      expect(screen.getAllByRole('button', { name: 'Ask without the project' })).toHaveLength(1);
    });
  });

  describe('announcing a failure', () => {
    it('announces a failure that arrives while the feed is open', () => {
      const asked = [user('Q?'), answer('', { status: 'pending' })];
      const { rerender } = renderFeed({ messages: asked, isPending: true });
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();

      rerender({ messages: [asked[0], failure(503, { id: asked[1].id })], isPending: false });

      expect(screen.getByRole('alert')).toHaveTextContent('The assistant is temporarily unavailable.');
    });

    it('does not announce a failure that was already there when the feed opened', () => {
      renderFeed({ messages: [user('Q?'), failure(503)] });

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(screen.getByText('The assistant is temporarily unavailable.')).toBeInTheDocument();
    });

    it('announces the failure of a retry that fails again', () => {
      const first = [user('Q?'), failure(503)];
      const { rerender } = renderFeed({ messages: first });

      rerender({ messages: [...first, user('Q?'), failure(503)] });

      expect(screen.getAllByRole('alert')).toHaveLength(1);
    });
  });

  describe('rendering cost', () => {
    it('does not render a settled answer again while a later one streams', () => {
      const settled = [user('Q1'), answer('A settled answer.')];
      const asked = user('Q2');
      const streaming = answer('To', { status: 'pending' });
      const { rerender } = renderFeed({ messages: [...settled, asked, streaming], isPending: true });
      markdownRenders.mockClear();

      rerender({ messages: [...settled, asked, { ...streaming, content: 'To a' }], isPending: true, pendingSeconds: 1 });
      rerender({ messages: [...settled, asked, { ...streaming, content: 'To a to' }], isPending: true, pendingSeconds: 2 });

      const rendered = markdownRenders.mock.calls.map(([content]) => content);
      expect(rendered).not.toContain('A settled answer.');
      expect(rendered).toContain('To a to');
    });
  });

  describe('scrolling', () => {
    function geometry(element: HTMLElement, { scrollHeight, clientHeight, scrollTop }: Record<string, number>) {
      Object.defineProperty(element, 'scrollHeight', { value: scrollHeight, configurable: true });
      Object.defineProperty(element, 'clientHeight', { value: clientHeight, configurable: true });
      element.scrollTop = scrollTop;
    }

    const asked = user('Q?');
    const streaming = answer('Some', { status: 'pending' });

    it('starts at the bottom of a restored conversation', () => {
      vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockReturnValue(777);

      renderFeed({ messages: [user('Q?'), answer('A.')] });

      expect(log().scrollTop).toBe(777);
    });

    it('follows new content while the user is at the bottom', () => {
      const { rerender } = renderFeed({ messages: [asked, streaming], isPending: true });
      geometry(log(), { scrollHeight: 1000, clientHeight: 400, scrollTop: 560 });
      fireEvent.scroll(log());

      rerender({ messages: [asked, { ...streaming, content: 'Some more' }], isPending: true });

      expect(log().scrollTop).toBe(1000);
    });

    it('leaves the scroll alone once the user has gone up to read', () => {
      const { rerender } = renderFeed({ messages: [asked, streaming], isPending: true });
      geometry(log(), { scrollHeight: 1000, clientHeight: 400, scrollTop: 100 });
      fireEvent.scroll(log());

      rerender({ messages: [asked, { ...streaming, content: 'Some more' }], isPending: true });

      expect(log().scrollTop).toBe(100);
    });

    it('counts 48 px from the bottom as the bottom, and 49 as away', () => {
      const { rerender } = renderFeed({ messages: [asked, streaming], isPending: true });
      geometry(log(), { scrollHeight: 1000, clientHeight: 400, scrollTop: 552 });
      fireEvent.scroll(log());
      rerender({ messages: [asked, { ...streaming, content: 'Some more' }], isPending: true });
      expect(log().scrollTop).toBe(1000);

      geometry(log(), { scrollHeight: 2000, clientHeight: 400, scrollTop: 1551 });
      fireEvent.scroll(log());
      rerender({ messages: [asked, { ...streaming, content: 'Some more again' }], isPending: true });

      expect(log().scrollTop).toBe(1551);
    });

    it('brings the bottom back when the user sends a question, wherever they were', () => {
      const done = [user('Q0?'), answer('A0.')];
      const { rerender } = renderFeed({ messages: done });
      geometry(log(), { scrollHeight: 1000, clientHeight: 400, scrollTop: 0 });
      fireEvent.scroll(log());

      rerender({ messages: [...done, asked, answer('', { status: 'pending' })], isPending: true });

      expect(log().scrollTop).toBe(1000);
    });
  });

  describe('messages in the list', () => {
    it('keeps a message in place when one is added after it', () => {
      const first = [user('Q1'), answer('A1.')];
      const { rerender } = renderFeed({ messages: first });
      const before = within(log()).getByText('A1.');

      rerender({ messages: [...first, user('Q2'), answer('A2.')] });

      expect(within(log()).getByText('A1.')).toBe(before);
    });
  });
});
