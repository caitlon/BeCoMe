import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@tests/utils';
import userEvent from '@testing-library/user-event';
import { AssistantMarkdown } from '@/components/assistant/AssistantMarkdown';
import '@/components/assistant/i18n';

function renderMarkdown(
  content: string,
  props: Partial<React.ComponentProps<typeof AssistantMarkdown>> = {}
) {
  return render(<AssistantMarkdown content={content} messageId="m1" {...props} />);
}

describe('AssistantMarkdown', () => {
  afterEach(() => {
    window.location.hash = '';
  });

  it('renders paragraphs, lists, bold, italic and inline code', () => {
    const { container } = renderMarkdown('para\n\n- one\n- two\n\n1. first\n\n**bold** *it* `code`');

    expect(container.querySelectorAll('li')).toHaveLength(3);
    expect(container.querySelector('ul')).not.toBeNull();
    expect(container.querySelector('ol')).not.toBeNull();
    expect(screen.getByText('bold').tagName).toBe('STRONG');
    expect(screen.getByText('it').tagName).toBe('EM');
    expect(screen.getByText('code').tagName).toBe('CODE');
  });

  it('shows a heading as plain text, not as a heading element', () => {
    const { container } = renderMarkdown('# Title\n\nbody');

    expect(container.querySelector('h1')).toBeNull();
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    expect(container).toHaveTextContent('Title');
    expect(screen.getByText('body')).toBeInTheDocument();
  });

  it('shows a markdown link as its text, never as an anchor', () => {
    renderMarkdown('[the docs](https://docs.becomify.app/user/reading-the-result)');

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText('the docs')).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain('href=');
  });

  it('shows a javascript: link as its text only', () => {
    renderMarkdown('[click me](javascript:alert(1))');

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText('click me')).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain('javascript:');
  });

  it('shows an autolink as text', () => {
    renderMarkdown('see <https://example.com/x> now');

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(document.body).toHaveTextContent('https://example.com/x');
  });

  it('never renders an image, and its alt text and url never become an element', () => {
    const { container } = renderMarkdown('![secret-alt](https://evil.example/track.png?q=1)');

    expect(container.querySelector('img')).toBeNull();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(container.innerHTML).not.toContain('evil.example');
  });

  it('skips raw HTML instead of rendering it', () => {
    const { container } = renderMarkdown('<div data-testid="raw">hi</div>\n\n<script>alert(1)</script>\n\nafter');

    expect(screen.queryByTestId('raw')).not.toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
    expect(container).not.toHaveTextContent('<div');
    expect(container).not.toHaveTextContent('alert(1)');
    expect(screen.getByText('after')).toBeInTheDocument();
  });

  it('does not leak the hast node prop onto DOM elements', () => {
    const { container } = renderMarkdown('para [1]\n\n- item **bold** *it*', { sourceNumbers: [1] });

    expect(container.querySelector('[node]')).toBeNull();
  });

  it('does not render tables, blockquotes or code blocks as their own elements', () => {
    const { container } = renderMarkdown('> quoted\n\n```\nfenced\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |');

    expect(container.querySelector('blockquote')).toBeNull();
    expect(container.querySelector('pre')).toBeNull();
    expect(container.querySelector('table')).toBeNull();
    expect(screen.getByText('quoted')).toBeInTheDocument();
  });

  describe('citation markers', () => {
    it('turns [n] with a source into an in-page anchor with the exact href', () => {
      renderMarkdown('The compromise is 3.4 [1].', { sourceNumbers: [1, 2] });

      const cite = screen.getByRole('link', { name: '[1]' });
      expect(cite).toHaveAttribute('href', '#assistant-src-m1-1');
      expect(cite).not.toHaveAttribute('target');
      expect(cite).not.toHaveAttribute('node');
    });

    it('calls onCite and leaves location.hash alone when a citation is clicked', async () => {
      const onCite = vi.fn();
      renderMarkdown('Claim [2].', { sourceNumbers: [2], onCite });

      await userEvent.click(screen.getByRole('link', { name: '[2]' }));

      expect(onCite).toHaveBeenCalledExactlyOnceWith(2);
      expect(window.location.hash).toBe('');
    });

    it('clicking a citation works without an onCite handler', async () => {
      renderMarkdown('Claim [2].', { sourceNumbers: [2] });

      await userEvent.click(screen.getByRole('link', { name: '[2]' }));

      expect(window.location.hash).toBe('');
    });

    it('strikes through [n] without a source: no link, not focusable, hint for screen readers', () => {
      renderMarkdown('Claim [4].', { sourceNumbers: [1] });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      const marker = screen.getByText('[4]');
      expect(marker.closest('s')).not.toBeNull();
      expect(marker.closest('s')).not.toHaveAttribute('tabindex');
      expect(document.body).toHaveTextContent('No such source');
    });

    it('treats every [n] as struck through when there are no sources at all', () => {
      renderMarkdown('Claim [1].');

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.getByText('[1]').closest('s')).not.toBeNull();
    });

    it('finds citations inside list items, bold and italic text', () => {
      renderMarkdown('- item [1]\n\n**bold [2]** and *it [3]*', { sourceNumbers: [1, 2, 3] });

      expect(screen.getAllByRole('link').map((a) => a.textContent)).toEqual(['[1]', '[2]', '[3]']);
    });

    it('keeps several markers and the text around them in order', () => {
      const { container } = renderMarkdown('a [1] b [2] c', { sourceNumbers: [1, 2] });

      expect(container.textContent).toBe('a [1] b [2] c');
    });

    it('leaves [1] literal inside inline code', () => {
      renderMarkdown('use `arr[1]` here', { sourceNumbers: [1] });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.getByText('arr[1]').tagName).toBe('CODE');
    });

    it.each(['[0]', '[-1]', '[1.5]', '[a]', '[]', '[01]'])('does not treat %s as a citation', (marker) => {
      const { container } = renderMarkdown(`x ${marker} y`, { sourceNumbers: [0, 1] });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(container.querySelector('s')).toBeNull();
      expect(container.textContent).toContain(marker);
    });
  });
});
