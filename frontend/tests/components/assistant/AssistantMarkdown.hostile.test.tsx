import { describe, it, expect } from 'vitest';
import { render } from '@tests/utils';
import { AssistantMarkdown } from '@/components/assistant/AssistantMarkdown';
import { sourceAnchorId } from '@/components/assistant/message-shape';
import '@/components/assistant/i18n';

// Pins the element allowlist of AssistantMarkdown against markup in a model's answer. In
// production nginx's Content-Security-Policy limits images, frames and scripts to the app's
// and the API's origins (`img-src 'self' data:__API_ORIGIN__`, where __API_ORIGIN__ is the
// API origin filled in at deploy), but it does not stop a link from navigating, so these
// tests pin the allowlist on its own. Whatever a hostile or half-streamed answer contains,
// the rendered tree holds no link that leaves the page, no image or embed, and no
// element with an event handler, a style or a source, because any of them could
// fetch or leak data from the reader's browser.

const FORBIDDEN_ELEMENTS = 'img, script, iframe, object, embed, video, audio, source, svg';

function expectNothingOutbound(container: HTMLElement) {
  expect(container.querySelector('a[href]:not([href^="#"])')).toBeNull();
  expect(container.querySelector(FORBIDDEN_ELEMENTS)).toBeNull();
  expect(container.querySelector('[style], [src]')).toBeNull();
  for (const element of container.querySelectorAll('*')) {
    const handlers = Array.from(element.attributes).filter((attr) => attr.name.startsWith('on'));
    expect(handlers).toEqual([]);
  }
}

function renderAnswer(content: string, sourceNumbers?: number[]) {
  return render(<AssistantMarkdown content={content} messageId="m1" sourceNumbers={sourceNumbers} />);
}

describe('AssistantMarkdown against hostile answers', () => {
  describe('markup an answer can carry', () => {
    it.each([
      ['an entity-encoded javascript: link', '[x](&#106;avascript:alert(1))', 'x'],
      ['a reference-style link to javascript:', '[x][r]\n\n[r]: javascript:alert(1)', 'x'],
      ['a reference-style link to https', '[x][r]\n\n[r]: https://evil.example/', 'x'],
      ['a reference-style image', '![a][r]\n\n[r]: https://evil.example/i.png', undefined],
      ['an image inside a link', '[![a](https://evil.example/i.png)](https://evil.example/)', undefined],
      ['a data: svg image', '![x](data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=)', undefined],
      ['an https autolink literal', 'see https://evil.example/?d=secret now', 'https://evil.example/?d=secret'],
      ['a bare www autolink literal', 'see www.evil.example now', 'www.evil.example'],
      ['a raw anchor tag', '<a href="https://evil.example">x</a>', '<a href="https://evil.example">x</a>'],
      ['an entity-encoded img tag', '&lt;img src=x onerror=alert(1)&gt;', '<img src=x onerror=alert(1)>'],
      ['a raw svg tag', '<svg onload=alert(1)></svg>', '<svg onload=alert(1)></svg>'],
      ['a raw iframe tag', '<iframe src="https://evil.example"></iframe>', '<iframe src="https://evil.example"></iframe>'],
    ])('renders nothing that fetches or navigates for %s', (_label, content, visibleText) => {
      const { container } = renderAnswer(content, [1]);

      expectNothingOutbound(container);
      if (visibleText !== undefined) {
        expect(container.textContent).toContain(visibleText);
      }
    });
  });

  describe('an answer streamed in', () => {
    const answer = [
      'Intro [a link](https://evil.example/?d=secret) and',
      '![a pic](https://evil.example/i.png) then',
      '<img src=x onerror=alert(1)> and <https://evil.example/x> see [1].',
      '',
      '[1]: https://evil.example/ref "Title"',
    ].join('\n');

    it.each([
      ['with sources', [1]],
      ['without sources', undefined],
    ])('holds nothing outbound at any prefix (%s)', (_label, sourceNumbers) => {
      const { container, rerender } = render(
        <AssistantMarkdown content="" messageId="m1" sourceNumbers={sourceNumbers} />
      );

      for (let i = 1; i <= answer.length; i += 1) {
        rerender(<AssistantMarkdown content={answer.slice(0, i)} messageId="m1" sourceNumbers={sourceNumbers} />);
        expectNothingOutbound(container);
      }

      // Every link left is a citation, and its href is the one the component builds.
      const links = container.querySelectorAll('a[href]');
      for (const link of links) {
        expect(link.getAttribute('href')).toBe(`#${sourceAnchorId('m1', 1)}`);
      }
      // Not vacuous: with sources the citation link is there, without them none is.
      if (sourceNumbers === undefined) {
        expect(links.length).toBe(0);
      } else {
        expect(links.length).toBeGreaterThan(0);
      }
    });
  });

  describe('a fence info string with entity-encoded spaces', () => {
    it('adds no class beyond the language one', () => {
      const { container } = renderAnswer('```js&#32;fixed&#32;inset-0\ncode\n```');

      const code = container.querySelector('code');
      expect(code).not.toBeNull();
      expect(Array.from(code?.classList ?? [])).toEqual(['language-js']);
      expect(container.querySelector('pre')).toBeNull();
      expectNothingOutbound(container);
    });
  });

  describe('markdown left behind by the server-side citation removal', () => {
    it.each([
      ['an image whose bracket was removed from its alt text', '![x](https://evil.example/p.png)'],
      ['a link whose name bracket was removed in front of it', 'See[data](https://evil.example/u)'],
      ['a link beside a bracket that lost its name', 'See [x] and [data](https://evil.example/u)'],
    ])('renders nothing outbound for %s', (_label, content) => {
      const { container } = renderAnswer(content, [1]);

      expectNothingOutbound(container);
      expect(container.innerHTML).not.toContain('evil.example');
    });
  });
});
