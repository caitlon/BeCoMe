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
    projectScoped: true,
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

      expect(within(log()).getByText('Answering…')).toBeInTheDocument();
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

      expect(within(log()).getByText(label)).toBeInTheDocument();
    });

    it('names two phases, not three, in a conversation that has no project to read', () => {
      const { rerender } = renderFeed({
        messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: 4, projectScoped: false,
      });
      expect(within(log()).getByText('Searching the documentation…')).toBeInTheDocument();
      expect(within(log()).queryByText('Reading the project…')).not.toBeInTheDocument();

      rerender({ messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: 8, projectScoped: false });

      expect(within(log()).getByText('Writing the answer. This can take up to a minute.')).toBeInTheDocument();
    });

    it('treats agent mode like hybrid', () => {
      renderFeed({ messages: waiting, isPending: true, mode: 'agent', pendingSeconds: 4 });

      expect(within(log()).getByText('Reading the project…')).toBeInTheDocument();
    });

    it('puts the streaming cursor on the text itself and shows no indicator once text has come', () => {
      const { container } = renderFeed({
        messages: [user('Q'), answer('The best comp', { status: 'pending' })],
        isPending: true,
      });

      const text = within(log()).getByText('The best comp');
      expect(text.parentElement?.className).toContain('[&>:last-child:not(ul,ol)]:after:animate-pulse');
      expect(text.parentElement?.className).toContain('[&>:is(ul,ol):last-child>li:last-child]:after:animate-pulse');
      expect(within(log()).queryByText('Answering…')).not.toBeInTheDocument();
      expect(container.querySelector('.animate-spin')).not.toBeInTheDocument();
    });

    it('takes the cursor away when the answer is done', () => {
      renderFeed({ messages: [user('Q'), answer('Done.')] });

      expect(within(log()).getByText('Done.').parentElement?.className).not.toContain('after:animate-pulse');
    });

    describe('announcement for a screen reader', () => {
      const status = () => screen.getByRole('status');

      it('lives outside the busy log, and says nothing while no turn runs', () => {
        renderFeed({ messages: [user('Q'), answer('A.')] });

        expect(log()).not.toContainElement(status());
        expect(status()).toBeEmptyDOMElement();
      });

      it('names the phase, and changes its text only when the phase changes', () => {
        const mutations: string[] = [];
        const { rerender } = renderFeed({ messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: 0 });
        const observer = new MutationObserver((records) =>
          records.forEach(() => mutations.push(status().textContent ?? ''))
        );
        observer.observe(status(), { childList: true, characterData: true, subtree: true });
        expect(status()).toHaveTextContent(/^Searching the documentation$/);

        for (const seconds of [1, 2]) {
          rerender({ messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: seconds });
        }
        expect(observer.takeRecords()).toHaveLength(0);

        rerender({ messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: 3 });
        expect(status()).toHaveTextContent(/^Reading the project$/);
        observer.disconnect();
      });

      it('is silent again once the answer has arrived', () => {
        const { rerender } = renderFeed({ messages: waiting, isPending: true, mode: 'hybrid' });
        expect(status()).toHaveTextContent(/^Searching the documentation$/);

        rerender({ messages: [waiting[0], answer('A.')], isPending: false, mode: 'hybrid' });

        expect(status()).toBeEmptyDOMElement();
      });
    });

    it('speaks Czech', async () => {
      await i18n.changeLanguage('cs');
      renderFeed({ messages: waiting, isPending: true, mode: 'hybrid', pendingSeconds: 9 });

      expect(within(screen.getByRole('log')).getByText('Píšu odpověď. Může to trvat až minutu.')).toBeInTheDocument();
    });
  });

  describe('history separator', () => {
    const thread = [
      user('q0'), answer('a0'), user('q1'), answer('a1'), user('q2'), answer('a2'),
    ];

    it('is drawn right before the oldest message the next request carries', () => {
      renderFeed({ messages: thread, historyWindowStart: 2 });

      const separator = screen.getByRole('separator', {
        name: 'Older messages are no longer sent with new questions.',
      });
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

      expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });

    it('offers the retry on the first render for a Retry-After of 0', () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
      vi.setSystemTime(1_000_000);
      renderFeed({
        messages: [
          user('Q?'),
          failure(429, { createdAt: 1_000_000, error: { code: 429, detail: 'x', retryAfter: 0 } }),
        ],
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

    it('offers only the project list when the conversation is not about a project', () => {
      renderFeed({ messages: [user('Q?'), failure(404)], projectScoped: false });

      expect(screen.queryByRole('button', { name: 'Ask without the project' })).not.toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Open projects' })).toBeInTheDocument();
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

  describe('rendering cost of the last answer', () => {
    it('does not render a cut answer that has a retry again when only the clock moved', () => {
      const messages = [user('Q?'), answer('Half of the answer', { status: 'cut' })];
      const onRetry = vi.fn();
      const { rerender } = renderFeed({ messages, onRetry });
      expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
      markdownRenders.mockClear();

      rerender({ messages, onRetry, pendingSeconds: 5 });
      rerender({ messages, onRetry, pendingSeconds: 6 });

      expect(markdownRenders).not.toHaveBeenCalled();
    });

    it('does the same for a missing project that has its actions', () => {
      const messages = [user('Q?'), failure(404, { content: 'Some text' })];
      const { rerender } = renderFeed({ messages });
      markdownRenders.mockClear();

      rerender({ messages, pendingSeconds: 5 });

      expect(markdownRenders).not.toHaveBeenCalled();
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

    it('follows the first content that arrives in a feed that opened with none from the user', () => {
      const { rerender } = renderFeed({ messages: [answer('A.')] });
      vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockReturnValue(500);

      rerender({ messages: [answer('A. And more.')] });

      expect(log().scrollTop).toBe(500);
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

  describe('edges', () => {
    it('renders an empty log for no messages', () => {
      renderFeed({ messages: [] });

      expect(log().firstElementChild?.children).toHaveLength(0);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('shows a cut answer that has no text as the block alone, with its retry', async () => {
      const { feedProps } = renderFeed({ messages: [user('Q?'), answer('', { status: 'cut' })] });

      expect(screen.getByText('The connection dropped before the answer finished.')).toBeInTheDocument();
      expect(screen.queryByText(/What arrived is shown above/)).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
      expect(feedProps.onRetry).toHaveBeenCalledWith('Q?');
    });
  });

  describe('messages in the list', () => {
    it('keeps a message where it is when an earlier one is removed, because each is keyed by its id', () => {
      const [q1, a1, q2, a2] = [user('Q1'), answer('A1.'), user('Q2'), answer('A2.')];
      const { rerender } = renderFeed({ messages: [q1, a1, q2, a2] });
      const before = within(log()).getByText('A2.');

      rerender({ messages: [q2, a2] });

      expect(within(log()).getByText('A2.')).toBe(before);
    });
  });
});
