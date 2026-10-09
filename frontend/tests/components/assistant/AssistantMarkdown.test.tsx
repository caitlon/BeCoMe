import { describe, it, expect, vi, afterEach } from 'vitest';
import { useState } from 'react';
import { fireEvent, render, screen } from '@tests/utils';
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
    expect(container.textContent).not.toContain('secret-alt');
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

  it.each(['one  \ntwo', 'one\\\ntwo'])('keeps a hard line break (%j) as a <br>', (content) => {
    const { container } = renderMarkdown(content);

    expect(container.querySelectorAll('p br')).toHaveLength(1);
  });

  it('keeps the same first paragraph node while the content grows, as a stream does', () => {
    const { container, rerender } = renderMarkdown('First paragraph');
    const paragraph = container.querySelector('p');

    rerender(<AssistantMarkdown content={'First paragraph grows\n\nSecond'} messageId="m1" />);

    expect(container.querySelector('p')).toBe(paragraph);
    expect(paragraph).toHaveTextContent('First paragraph grows');
    expect(container.querySelectorAll('p')).toHaveLength(2);
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

    it('prevents the default navigation of a citation click itself', () => {
      renderMarkdown('Claim [2].', { sourceNumbers: [2], onCite: vi.fn() });

      // fireEvent returns false when a listener called preventDefault.
      expect(fireEvent.click(screen.getByRole('link', { name: '[2]' }))).toBe(false);
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
      expect(marker.closest('s')).not.toHaveAttribute('title');
      expect(document.body).toHaveTextContent('No such source');
    });

    it('gives the unknown marker a line-through that no-underline does not cancel', () => {
      renderMarkdown('Claim [4].', { sourceNumbers: [1] });

      const cls = screen.getByText('[4]').closest('s')?.className ?? '';
      expect(cls).toContain('line-through');
      expect(cls).not.toContain('no-underline');
    });

    it('shows a huge marker literally and struck through, even when it is in the sources', () => {
      const { container } = renderMarkdown('Claim [99999999999999999999].', { sourceNumbers: [1e20] });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.getByText('[99999999999999999999]').closest('s')).not.toBeNull();
      expect(container.textContent).not.toContain('e+20');
    });

    it.each(['***[1]***', '**bold *[1]***'])('makes a citation inside nested emphasis (%s) the anchor', (content) => {
      renderMarkdown(content, { sourceNumbers: [1] });

      expect(screen.getByRole('link', { name: '[1]' })).toHaveAttribute('href', '#assistant-src-m1-1');
    });

    it('keeps the same DOM nodes when sourceNumbers and onCite are fresh on every render', () => {
      const { rerender } = renderMarkdown('Claim [1] here.', { sourceNumbers: [1], onCite: vi.fn() });
      const link = screen.getByRole('link', { name: '[1]' });
      const paragraph = link.closest('p');

      rerender(<AssistantMarkdown content="Claim [1] here." messageId="m1" sourceNumbers={[1]} onCite={vi.fn()} />);

      expect(screen.getByRole('link', { name: '[1]' })).toBe(link);
      expect(link.closest('p')).toBe(paragraph);
      expect(screen.getByText(/Claim/)).toBe(paragraph);
    });

    it('uses the new onCite after a rerender', async () => {
      const first = vi.fn();
      const second = vi.fn();
      const { rerender } = renderMarkdown('Claim [1].', { sourceNumbers: [1], onCite: first });

      rerender(<AssistantMarkdown content="Claim [1]." messageId="m1" sourceNumbers={[1]} onCite={second} />);
      await userEvent.click(screen.getByRole('link', { name: '[1]' }));

      expect(first).not.toHaveBeenCalled();
      expect(second).toHaveBeenCalledExactlyOnceWith(1);
    });

    describe('in a parent that re-renders on every cite', () => {
      function Parent() {
        const [count, setCount] = useState(0);
        return (
          <>
            <output>{count}</output>
            <AssistantMarkdown
              content="Claim [1]."
              messageId="m1"
              sourceNumbers={[1]}
              onCite={() => setCount((c) => c + 1)}
            />
          </>
        );
      }

      it('keeps focus on the citation after a click', async () => {
        render(<Parent />);
        const link = screen.getByRole('link', { name: '[1]' });

        await userEvent.click(link);

        expect(screen.getByRole('status')).toHaveTextContent('1');
        expect(document.activeElement).toBe(link);
      });

      it('keeps focus on the citation after Enter', async () => {
        render(<Parent />);
        const link = screen.getByRole('link', { name: '[1]' });
        link.focus();

        await userEvent.keyboard('{Enter}');

        expect(screen.getByRole('status')).toHaveTextContent('1');
        expect(document.activeElement).toBe(link);
      });
    });

    it('treats every [n] as struck through when the sources are known to be empty', () => {
      renderMarkdown('Claim [1].', { sourceNumbers: [] });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.getByText('[1]').closest('s')).not.toBeNull();
      expect(document.body).toHaveTextContent('No such source');
    });

    it('leaves [n] as plain text while the sources are not known yet', () => {
      const { container } = renderMarkdown('Claim [1] and **bold [2]**.');

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(container.querySelector('s')).toBeNull();
      expect(container.textContent).toBe('Claim [1] and bold [2].');
    });

    it('finds citations inside list items, bold and italic text', () => {
      renderMarkdown('- item [1]\n\n**bold [2]** and *it [3]*', { sourceNumbers: [1, 2, 3] });

      expect(screen.getAllByRole('link').map((a) => a.textContent)).toEqual(['[1]', '[2]', '[3]']);
    });

    it('keeps several markers and the text around them in order', () => {
      const { container } = renderMarkdown('a [1] b [2] c', { sourceNumbers: [1, 2] });

      expect(container.textContent).toBe('a [1] b [2] c');
    });

    it.each([
      ['See [1][2].', ['[1]', '[2]']],
      ['[1] opens the line', ['[1]']],
    ])('turns the citations in %j into anchors in order', (content, names) => {
      renderMarkdown(content, { sourceNumbers: [1, 2] });

      expect(screen.getAllByRole('link').map((a) => a.textContent)).toEqual(names);
    });

    it('keeps the citation anchor node while the content grows', () => {
      const { rerender } = renderMarkdown('A [1].', { sourceNumbers: [1] });
      const cite = screen.getByRole('link', { name: '[1]' });

      rerender(<AssistantMarkdown content="A [1]. More" messageId="m1" sourceNumbers={[1]} />);

      expect(screen.getByRole('link', { name: '[1]' })).toBe(cite);
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
