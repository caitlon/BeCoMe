import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, within } from '@tests/utils';
import userEvent from '@testing-library/user-event';
import i18n from '@/i18n';
import { AssistantMessage } from '@/components/assistant/AssistantMessage';
import type { AssistantMessage as Message } from '@/components/assistant/useAssistantChat';
import '@/components/assistant/i18n';

const base: Message = {
  id: 'm1',
  role: 'assistant',
  content: 'The answer is 42 [1].',
  status: 'done',
  createdAt: 1,
};

const publicSource = {
  n: 1,
  title: 'Reading the result',
  section: 'Confidence',
  snippet: 'Quote from **the page**',
  url: 'https://docs.becomify.app/user/reading-the-result',
  layer: 'public' as const,
};
const localSource = {
  n: 2,
  title: 'BeCoMe article',
  section: 'Introduction',
  snippet: 'Quote from the article',
  url: null,
  layer: 'local' as const,
};

function renderMessage(message: Partial<Message>, onRetry?: () => void) {
  return render(<AssistantMessage message={{ ...base, ...message }} onRetry={onRetry} />);
}

const rowButton = (name: RegExp) => screen.getByRole('button', { name });
const originalScrollIntoView = Element.prototype.scrollIntoView;

describe('AssistantMessage', () => {
  afterEach(async () => {
    Element.prototype.scrollIntoView = originalScrollIntoView;
    await i18n.changeLanguage('en');
  });

  describe('text', () => {
    it("renders the user's own message as plain text, not through markdown", () => {
      const { container } = renderMessage({ role: 'user', content: '**not bold**\n# not a heading' });

      expect(container.querySelector('strong')).toBeNull();
      expect(container.querySelector('h1')).toBeNull();
      expect(container.firstElementChild).toHaveClass('whitespace-pre-wrap');
      expect(container).toHaveTextContent('**not bold**');
    });

    it('renders an assistant answer through markdown', () => {
      renderMessage({ content: 'It is **bold**.' });

      expect(screen.getByText('bold').tagName).toBe('STRONG');
    });

    it('keeps the line breaks of a fenced code block', () => {
      const { container } = renderMessage({ content: '```\nline1\nline2\n```' });

      const code = container.querySelector('code');
      expect(code?.textContent).toBe('line1\nline2\n');
      expect(code?.closest('[class*="[&_code]:whitespace-pre-wrap"]')).not.toBeNull();
    });

    it('renders the content so far for a pending message', () => {
      renderMessage({ status: 'pending', content: 'partial words' });

      expect(screen.getByText('partial words')).toBeInTheDocument();
    });
  });

  describe('sources', () => {
    it('renders compact rows with number, title and section, each with an id', () => {
      const { container } = renderMessage({ sources: [publicSource, localSource] });

      expect(rowButton(/\[1\].*Reading the result.*Confidence/)).toHaveAttribute('aria-expanded', 'false');
      expect(rowButton(/\[2\].*BeCoMe article.*Introduction/)).toBeInTheDocument();
      expect(container.querySelector('#assistant-src-m1-1')).not.toBeNull();
      expect(container.querySelector('#assistant-src-m1-2')).not.toBeNull();
      expect(screen.queryByText(/Quote from/)).not.toBeInTheDocument();
    });

    it('expands a row on click and collapses it on the second click', async () => {
      renderMessage({ sources: [publicSource] });
      const button = rowButton(/Reading the result/);

      await userEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(document.getElementById(button.getAttribute('aria-controls') as string)).toHaveTextContent('Quote from');

      await userEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByText(/Quote from/)).not.toBeInTheDocument();
    });

    it('keeps only one row open: opening another closes the first', async () => {
      renderMessage({ sources: [publicSource, localSource] });

      await userEvent.click(rowButton(/Reading the result/));
      await userEvent.click(rowButton(/BeCoMe article/));

      expect(rowButton(/Reading the result/)).toHaveAttribute('aria-expanded', 'false');
      expect(rowButton(/BeCoMe article/)).toHaveAttribute('aria-expanded', 'true');
      expect(screen.queryByText(/Quote from \*\*the page\*\*/)).not.toBeInTheDocument();
      expect(screen.getByText(/Quote from the article/)).toBeInTheDocument();
    });

    it.each([
      ['markdown', 'Quote from **the page**', 'strong'],
      ['HTML', '<img src=x onerror=alert(1)>', 'img'],
    ])('shows a snippet with %s as literal text, never as an element', async (_label, snippet, tag) => {
      const { container } = renderMessage({ sources: [{ ...publicSource, snippet }] });

      await userEvent.click(rowButton(/Reading the result/));

      expect(screen.getByText(snippet)).toBeInTheDocument();
      expect(container.querySelector(tag)).toBeNull();
    });

    it('gives a public https source a safe link when expanded', async () => {
      renderMessage({ sources: [publicSource] });
      expect(screen.queryByRole('link', { name: 'Open the page' })).not.toBeInTheDocument();

      await userEvent.click(rowButton(/Reading the result/));

      const link = screen.getByRole('link', { name: 'Open the page' });
      expect(link).toHaveAttribute('href', publicSource.url);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
      expect(screen.getByText('Documentation')).toBeInTheDocument();
    });

    it.each([
      ['http:', 'http://docs.becomify.app/user'],
      ['javascript:', 'javascript:alert(1)'],
      ['a relative path', '/user/reading'],
      ['null', null],
    ])('renders a public source with a %s url as text, with no link', async (_label, url) => {
      renderMessage({ sources: [{ ...publicSource, url }] });

      await userEvent.click(rowButton(/Reading the result/));

      expect(screen.queryByRole('link', { name: 'Open the page' })).not.toBeInTheDocument();
      expect(screen.getByText(/Quote from/)).toBeInTheDocument();
    });

    it('never links a local source, even when it carries a url, and shows the badge and hint', async () => {
      renderMessage({ sources: [{ ...localSource, url: 'https://example.com/leak' }] });

      expect(screen.getByText('Local copy')).toBeInTheDocument();
      await userEvent.click(rowButton(/BeCoMe article/));

      expect(screen.queryByRole('link', { name: 'Open the page' })).not.toBeInTheDocument();
      expect(document.body.innerHTML).not.toContain('example.com/leak');
      expect(screen.getAllByText(/private corpus/).length).toBeGreaterThan(0);
    });

    it('shows no Local copy badge for a public source', () => {
      renderMessage({ sources: [publicSource] });

      expect(screen.queryByText('Local copy')).not.toBeInTheDocument();
    });

    it('expands the source and scrolls its row into view when a citation is clicked', async () => {
      const scrollIntoView = vi.fn();
      Element.prototype.scrollIntoView = scrollIntoView;
      const { container } = renderMessage({ sources: [publicSource] });

      await userEvent.click(screen.getByRole('link', { name: '[1]' }));

      expect(rowButton(/Reading the result/)).toHaveAttribute('aria-expanded', 'true');
      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' });
      expect(scrollIntoView.mock.contexts[0]).toBe(container.querySelector('#assistant-src-m1-1'));
      expect(window.location.hash).toBe('');
    });

    it('scrolls only once the detail exists, and again when the open row is cited again', async () => {
      const detailAtCall: boolean[] = [];
      Element.prototype.scrollIntoView = vi.fn(() => {
        detailAtCall.push(document.getElementById('assistant-src-m1-1-detail') !== null);
      });
      renderMessage({ sources: [publicSource] });

      await userEvent.click(screen.getByRole('link', { name: '[1]' }));
      await userEvent.click(screen.getByRole('link', { name: '[1]' }));

      expect(detailAtCall).toEqual([true, true]);
    });

    it('still expands the source where scrollIntoView does not exist', async () => {
      // Some environments lack the method; the click must neither throw nor stop the expansion.
      Object.defineProperty(Element.prototype, 'scrollIntoView', { value: undefined, configurable: true, writable: true });
      const onError = vi.fn((event: ErrorEvent) => event.preventDefault());
      window.addEventListener('error', onError);
      renderMessage({ sources: [publicSource] });

      await userEvent.click(screen.getByRole('link', { name: '[1]' }));
      window.removeEventListener('error', onError);

      expect(onError).not.toHaveBeenCalled();
      expect(rowButton(/Reading the result/)).toHaveAttribute('aria-expanded', 'true');
    });

    it('strikes through a citation that no source backs', () => {
      renderMessage({ content: 'Claim [4].', sources: [publicSource] });

      expect(screen.queryByRole('link', { name: '[4]' })).not.toBeInTheDocument();
      expect(screen.getByText('[4]').closest('s')).not.toBeNull();
    });

    it.each(['pending', 'cut', 'cancelled', 'error'] as const)(
      'leaves a [1] in a %s answer as plain text, since its sources are not known',
      (status) => {
        const { container } = renderMessage({ status, content: 'See [1].', sources: [publicSource] });

        expect(container.querySelector('s')).toBeNull();
        expect(screen.queryByRole('link', { name: '[1]' })).not.toBeInTheDocument();
        expect(container).toHaveTextContent('See [1].');
        expect(container).not.toHaveTextContent('No such source');
      },
    );

    it('shows a source row without a dangling separator when its section is empty', () => {
      renderMessage({ sources: [{ ...publicSource, section: '' }] });

      expect(rowButton(/Reading the result/).textContent).toBe('[1]Reading the result');
    });

    it('drops malformed sources without throwing and keeps the good ones', () => {
      const sources = [
        { ...publicSource, title: undefined },
        { ...publicSource, n: '1' },
        { ...publicSource, n: 5, layer: 'evil' },
        null,
        'x',
        localSource,
        { ...localSource, title: 'Duplicate of 2' },
      ] as unknown as Message['sources'];

      renderMessage({ sources, content: 'text' });

      expect(screen.getAllByRole('button')).toHaveLength(1);
      expect(rowButton(/BeCoMe article/)).toBeInTheDocument();
      expect(screen.queryByText('Duplicate of 2')).not.toBeInTheDocument();
    });

    it('treats a source stored without a snippet as an empty quote', async () => {
      const older: Record<string, unknown> = { ...publicSource };
      delete older.snippet;
      const { container } = renderMessage({ sources: [older as unknown as typeof publicSource] });

      await userEvent.click(rowButton(/Reading the result/));

      expect(screen.getByRole('link', { name: 'Open the page' })).toBeInTheDocument();
      expect(container.querySelector('q')).toBeNull();
    });

    it.each(['nope', []])('renders no sources block for %j', (sources) => {
      renderMessage({ sources: sources as Message['sources'] });

      expect(screen.queryByText('Sources')).not.toBeInTheDocument();
    });
  });

  describe('checks', () => {
    it('shows one line with the numbers when numbers are not grounded', () => {
      renderMessage({ checks: { citations_valid: true, numbers_grounded: false, ungrounded_numbers: ['17', '4.5'] } });

      expect(screen.getByText('Numbers not confirmed by the sources: 17, 4.5')).toBeInTheDocument();
      expect(screen.queryByText(/points to no source/)).not.toBeInTheDocument();
    });

    it('shows the citation line when a citation is invalid', () => {
      renderMessage({ checks: { citations_valid: false, numbers_grounded: true, ungrounded_numbers: [] } });

      expect(screen.getByText('A citation points to no source.')).toBeInTheDocument();
      expect(screen.queryByText(/Numbers not confirmed/)).not.toBeInTheDocument();
    });

    it('shows both lines when both checks fail', () => {
      renderMessage({ checks: { citations_valid: false, numbers_grounded: false, ungrounded_numbers: ['1'] } });

      expect(screen.getByText(/Numbers not confirmed/)).toBeInTheDocument();
      expect(screen.getByText(/points to no source/)).toBeInTheDocument();
    });

    it.each([
      ['both checks pass', { citations_valid: true, numbers_grounded: true, ungrounded_numbers: [] }],
      ['the flags are not booleans', { citations_valid: 'false', numbers_grounded: 'false', ungrounded_numbers: [] }],
    ])('shows nothing when %s', (_label, checks) => {
      renderMessage({ checks: checks as unknown as Message['checks'] });

      expect(screen.queryByText(/Numbers not confirmed/)).not.toBeInTheDocument();
      expect(screen.queryByText(/points to no source/)).not.toBeInTheDocument();
    });

    it.each([
      ['en', 'Some numbers are not confirmed by the sources.'],
      ['cs', 'Některá čísla zdroje nepotvrzují.'],
    ])('shows a line without a list when numbers are not grounded but none are named (%s)', async (lang, text) => {
      await i18n.changeLanguage(lang);
      renderMessage({ checks: { citations_valid: true, numbers_grounded: false, ungrounded_numbers: [] } });

      expect(screen.getByText(text)).toBeInTheDocument();
    });
  });

  describe('tools line', () => {
    it('names the known tools with short labels', () => {
      renderMessage({
        toolsUsed: ['search_docs', 'list_my_projects', 'get_project', 'get_project_result', 'get_project_opinions'],
      });

      expect(screen.getByText('Read: documentation, projects, project, result, opinions')).toBeInTheDocument();
    });

    it('shows an unknown tool by its raw name', () => {
      renderMessage({ toolsUsed: ['made_up_tool', 'search_docs'] });

      expect(screen.getByText('Read: made_up_tool, documentation')).toBeInTheDocument();
    });

    it('keeps string tool names only', () => {
      renderMessage({ toolsUsed: ['search_docs', 7, null] as unknown as string[] });

      expect(screen.getByText('Read: documentation')).toBeInTheDocument();
    });

    it('shows no line for a non-array value or an empty list', () => {
      const { unmount } = renderMessage({ toolsUsed: 5 as unknown as string[] });
      expect(screen.queryByText(/^Read:/)).not.toBeInTheDocument();
      unmount();

      renderMessage({ toolsUsed: [] });
      expect(screen.queryByText(/^Read:/)).not.toBeInTheDocument();
    });
  });

  describe('failed turns', () => {
    const DETAIL = 'Traceback: db password hunter2 at /srv/app.py';

    it.each([
      [429, 120, 'Message limit reached. Try again in 2 min.'],
      [429, 61, 'Message limit reached. Try again in 2 min.'],
      [429, 30, 'Message limit reached. Try again in 1 min.'],
      [429, undefined, 'Message limit reached. Try again later.'],
      [429, 0, 'Message limit reached. Try again later.'],
      [429, -5, 'Message limit reached. Try again later.'],
      [429, Number.NaN, 'Message limit reached. Try again later.'],
      [429, Number.POSITIVE_INFINITY, 'Message limit reached. Try again later.'],
      [503, undefined, 'The assistant is temporarily unavailable.'],
      [404, undefined, 'This project is not available.'],
      [0, undefined, 'Something went wrong. Please try again.'],
      [500, undefined, 'Something went wrong. Please try again.'],
    ])('code %s with retryAfter %s shows a fixed message and never the detail', (code, retryAfter, text) => {
      renderMessage({ status: 'error', content: '', error: { code, detail: DETAIL, retryAfter } });

      expect(screen.getByText(text)).toBeInTheDocument();
      expect(document.body).not.toHaveTextContent('hunter2');
      expect(document.body).not.toHaveTextContent('Traceback');
    });

    it('adds a hint under the 503 and 404 messages', () => {
      const { unmount } = renderMessage({ status: 'error', content: '', error: { code: 503, detail: 'x' } });
      expect(screen.getByText('The model is not responding.')).toBeInTheDocument();
      unmount();

      renderMessage({ status: 'error', content: '', error: { code: 404, detail: 'x' } });
      expect(screen.getByText('It may have been deleted or you are no longer a member.')).toBeInTheDocument();
    });

    it('falls back to the generic message when an error message has no error object', () => {
      renderMessage({ status: 'error', content: '' });

      expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument();
    });

    it('keeps the partial text of a cut answer, muted, with the interrupted block under it', () => {
      const { container } = renderMessage({ status: 'cut', content: 'The best compromise is' });

      expect(screen.getByText('The best compromise is')).toBeInTheDocument();
      expect(container.querySelector('.opacity-75')).toContainElement(screen.getByText('The best compromise is'));
      expect(screen.getByText('The connection dropped before the answer finished.')).toBeInTheDocument();
      expect(screen.getByText(/What arrived is shown above/)).toBeInTheDocument();
    });

    it.each(['', '  \n'])('renders a cut answer with content %j as the block alone: no wrapper, no hint', (content) => {
      const { container } = renderMessage({ status: 'cut', content });

      expect(screen.getByText('The connection dropped before the answer finished.')).toBeInTheDocument();
      expect(screen.queryByText(/What arrived is shown above/)).not.toBeInTheDocument();
      expect(container.querySelector('.opacity-75')).toBeNull();
      expect(container.querySelector('p')?.textContent).toBe('The connection dropped before the answer finished.');
    });

    it('keeps the partial text of an error turn, muted, above the block', () => {
      const { container } = renderMessage({ status: 'error', content: 'half', error: { code: 503, detail: 'x' } });

      expect(container.querySelector('.opacity-75')).toContainElement(screen.getByText('half'));
      expect(screen.getByText('The assistant is temporarily unavailable.')).toBeInTheDocument();
    });

    it('offers a retry button on an error and on a cut answer when onRetry is passed', async () => {
      const onRetry = vi.fn();
      const { unmount } = renderMessage({ status: 'error', content: '', error: { code: 503, detail: 'x' } }, onRetry);

      await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
      expect(onRetry).toHaveBeenCalledTimes(1);
      unmount();

      renderMessage({ status: 'cut', content: 'partial' }, onRetry);
      await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
      expect(onRetry).toHaveBeenCalledTimes(2);
    });

    it('shows no retry button without onRetry', () => {
      renderMessage({ status: 'error', content: '', error: { code: 503, detail: 'x' } });

      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it('is an alert only when told to announce it', () => {
      const failed: Partial<Message> = { status: 'error', content: '', error: { code: 503, detail: 'x' } };
      const { unmount } = render(<AssistantMessage message={{ ...base, ...failed }} announce />);
      expect(screen.getByRole('alert')).toHaveTextContent('The assistant is temporarily unavailable.');
      unmount();

      render(<AssistantMessage message={{ ...base, ...failed }} />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('offers the two ways out of a missing project when given them, and not otherwise', async () => {
      const notFound = { onAskWithout: vi.fn(), onOpenProjects: vi.fn() };
      const gone: Partial<Message> = { status: 'error', content: '', error: { code: 404, detail: 'x' } };
      const { unmount } = render(<AssistantMessage message={{ ...base, ...gone }} notFound={notFound} />);

      await userEvent.click(screen.getByRole('button', { name: 'Ask without the project' }));
      await userEvent.click(screen.getByRole('link', { name: 'Open projects' }));

      expect(notFound.onAskWithout).toHaveBeenCalledTimes(1);
      expect(notFound.onOpenProjects).toHaveBeenCalledTimes(1);
      unmount();

      renderMessage(gone);
      expect(screen.queryByRole('button', { name: 'Ask without the project' })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Open projects' })).not.toBeInTheDocument();
    });
  });

  describe('cancelled', () => {
    it('shows the partial text muted with a Stopped note and no red block', () => {
      const { container } = renderMessage({ status: 'cancelled', content: 'half an answ' });

      expect(container.querySelector('.opacity-75')).toContainElement(screen.getByText('half an answ'));
      const note = screen.getByText('Stopped');
      expect(note).toBeInTheDocument();
      expect(within(note.parentElement as HTMLElement).getByText(/Not sent with your next question/)).toBeInTheDocument();
      expect(screen.queryByText(/connection dropped/)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
    });

    it.each(['', '  \n'])('shows Stopped without the partial-answer hint or a wrapper when the content is %j', (content) => {
      const { container } = renderMessage({ status: 'cancelled', content });

      expect(screen.getByText('Stopped')).toBeInTheDocument();
      expect(screen.queryByText(/Partial answer/)).not.toBeInTheDocument();
      expect(container.querySelector('.opacity-75')).toBeNull();
    });
  });

  describe('Czech', () => {
    beforeEach(async () => {
      await i18n.changeLanguage('cs');
    });

    it('speaks Czech in the sources, checks, tools and error copy', async () => {
      renderMessage({
        sources: [localSource],
        checks: { citations_valid: false, numbers_grounded: false, ungrounded_numbers: ['17'] },
        toolsUsed: ['get_project_result'],
      });

      expect(screen.getByText('Zdroje')).toBeInTheDocument();
      expect(screen.getByText('Místní kopie')).toBeInTheDocument();
      expect(screen.getByText('Čísla, která zdroje nepotvrzují: 17')).toBeInTheDocument();
      expect(screen.getByText('Citace odkazuje na neexistující zdroj.')).toBeInTheDocument();
      expect(screen.getByText('Načteno: výsledek')).toBeInTheDocument();
    });

    it('shows the Czech rate-limit message with the minutes', () => {
      renderMessage({ status: 'error', content: '', error: { code: 429, detail: 'x', retryAfter: 600 } });

      expect(screen.getByText('Limit zpráv vyčerpán. Zkuste to znovu za 10 min.')).toBeInTheDocument();
    });
  });
});
