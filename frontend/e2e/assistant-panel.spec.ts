import AxeBuilder from '@axe-core/playwright';
import type { Page, Request, Route } from '@playwright/test';

import { test, expect } from './fixtures/base';

// The panel exists only in a build made with VITE_ASSISTANT_ENABLED=true, which no CI
// job sets, so there the whole file is skipped. To run it, start the suite with the
// flag in the environment so the dev server Playwright launches picks it up:
//   VITE_ASSISTANT_ENABLED=true npx playwright test e2e/assistant-panel.spec.ts --project=chromium
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

const SOURCE = {
  n: 1,
  title: 'Reading the result',
  section: 'Best compromise',
  snippet: 'The best compromise is the midpoint of the mean and the median.',
  url: 'https://docs.becomify.app/user/reading-the-result#best-compromise',
  layer: 'public',
};

const ANSWER = {
  answer: 'The best compromise is the midpoint of the mean and the median [1].',
  sources: [SOURCE],
  tools_used: ['search_docs'],
  checks: { citations_valid: true, numbers_grounded: true, ungrounded_numbers: [] },
  usage: { input_tokens: 10, output_tokens: 12, total_tokens: 22, llm_calls: 1, complete: true },
  timing: { ttft_ms: 40, total_ms: 400 },
};

const PROJECT_ID = '6f1c2f0e-8f3b-4c55-9d6e-0a1b2c3d4e5f';
const PROJECT = {
  id: PROJECT_ID,
  name: 'Flood prevention',
  description: null,
  scale_min: 0,
  scale_max: 5,
  scale_unit: 'points',
  admin_id: USER.id,
  created_at: '2026-01-01T00:00:00Z',
  member_count: 1,
  is_example: false,
  role: 'admin',
};

const QUESTION = 'What does the result mean?';
const STREAM = '**/api/v1/assistant/chat/stream';
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

function sse(events: ReadonlyArray<readonly [string, unknown]>): string {
  return events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join('');
}

const streamed = (route: Route) =>
  route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: sse([
      ['token', { text: 'The best compromise ' }],
      ['token', { text: 'is the midpoint of the mean and the median [1].' }],
      ['done', ANSWER],
    ]),
  });

const refused = (status: number, headers: Record<string, string> = {}) => (route: Route) =>
  route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify({ detail: 'internal detail' }) });

const questionOf = (request: Request): string => (request.postDataJSON() as { message: string }).message;

/** Signs the app in and answers the config, with everything else a 404 so nothing reaches a server. */
async function mockApp(page: Page, onStream: (route: Route) => unknown) {
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'not mocked' }) })
  );
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ json: USER }));
  await page.route('**/api/v1/assistant/config', (route) => route.fulfill({ json: CONFIG }));
  await page.route(STREAM, onStream);
}

/** What the project page needs to stay on screen: any failed load sends the user back to the list. */
async function mockProject(page: Page) {
  await page.route(`**/api/v1/projects/${PROJECT_ID}`, (route) => route.fulfill({ json: PROJECT }));
  for (const part of ['opinions', 'members', 'invitations']) {
    await page.route(`**/api/v1/projects/${PROJECT_ID}/${part}`, (route) => route.fulfill({ json: [] }));
  }
}

async function openPanel(page: Page, path = '/about') {
  await page.goto(path);
  await page.getByRole('button', { name: 'Assistant' }).first().click();
  await expect(page.getByRole('dialog', { name: 'Assistant' })).toBeVisible();
}

const box = (page: Page) => page.getByRole('textbox', { name: 'Ask a question…' });

async function ask(page: Page) {
  await box(page).fill(QUESTION);
  await box(page).press('Enter');
}

/** The WCAG violations inside the open panel. */
async function auditDialog(page: Page) {
  return (await new AxeBuilder({ page }).include('[role="dialog"]').withTags(WCAG_TAGS).analyze()).violations;
}

test.describe('Assistant panel', () => {
  test('streams an answer and shows its source', async ({ page }) => {
    await mockApp(page, streamed);
    await openPanel(page);

    const requestSent = page.waitForRequest(STREAM);
    await ask(page);

    const body = (await requestSent).postDataJSON();
    expect(body).toMatchObject({ message: QUESTION, project_id: null, locale: 'en', history: [] });
    const feed = page.getByRole('log', { name: 'Conversation' });
    await expect(feed).toContainText(QUESTION);
    await expect(feed).toContainText('The best compromise is the midpoint of the mean and the median');
    await expect(feed.getByRole('button', { name: /Reading the result/ })).toBeVisible();
    await expect(box(page)).toHaveValue('');

    await feed.getByRole('button', { name: /Reading the result/ }).click();
    await expect(feed.getByText(SOURCE.snippet)).toBeVisible();

    expect(await auditDialog(page)).toEqual([]);
  });

  test('Stop ends a running answer, and Escape does not', async ({ page }) => {
    // Never answered: the request hangs until the page aborts it.
    await mockApp(page, () => new Promise(() => undefined));
    await openPanel(page);
    const aborted = page.waitForEvent('requestfailed', (request) => request.url().includes('/assistant/chat/stream'));

    await ask(page);
    const stop = page.getByRole('button', { name: 'Stop' });
    await expect(stop).toBeVisible();
    await expect(page.getByRole('log').getByText('Answering…')).toBeVisible();
    await expect(page.getByRole('dialog').getByRole('status')).toHaveText('Answering');
    await expect(box(page)).toBeEnabled();

    await page.keyboard.press('Escape');
    // A closing sheet stays in the DOM through its exit animation, so "visible" alone would
    // pass a sheet that has begun to close: wait out the animation, then read the state.
    await page.waitForTimeout(500);
    await expect(page.getByRole('dialog', { name: 'Assistant' })).toHaveAttribute('data-state', 'open');
    await expect(stop).toBeVisible();

    await stop.click();
    expect((await aborted).failure()?.errorText).toMatch(/abort/i);
    await expect(page.getByText('Stopped')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Send' })).toBeVisible();
  });

  test('a rate limit names the wait and puts the question back in the box', async ({ page }) => {
    await mockApp(page, refused(429, { 'Retry-After': '2520' }));
    await openPanel(page);

    await ask(page);

    await expect(page.getByText('Message limit reached. Try again in 42 min.')).toBeVisible();
    await expect(box(page)).toHaveValue(QUESTION);
    await expect(page.getByRole('button', { name: 'Try again' })).toHaveCount(0);
    await expect(page.getByText('internal detail')).toHaveCount(0);
  });

  test('a rate limit with no Retry-After, as the API sends it, offers Try again at once', async ({ page }) => {
    let calls = 0;
    await mockApp(page, (route) => (++calls === 1 ? refused(429)(route) : streamed(route)));
    await openPanel(page);

    await ask(page);

    await expect(page.getByText('Message limit reached. Try again later.')).toBeVisible();
    await expect(box(page)).toHaveValue(QUESTION);
    const retried = page.waitForRequest(STREAM);
    await page.getByRole('button', { name: 'Try again' }).click();

    expect(questionOf(await retried)).toBe(QUESTION);
    await expect(page.getByRole('log')).toContainText('is the midpoint of the mean and the median');
  });

  test('an unavailable model keeps the question and Try again re-sends it', async ({ page }) => {
    let calls = 0;
    await mockApp(page, (route) => (++calls === 1 ? refused(503)(route) : streamed(route)));
    await openPanel(page);

    await ask(page);
    await expect(page.getByText('The assistant is temporarily unavailable.')).toBeVisible();
    await expect(box(page)).toHaveValue(QUESTION);

    const retried = page.waitForRequest(STREAM);
    await page.getByRole('button', { name: 'Try again' }).click();

    expect(questionOf(await retried)).toBe(QUESTION);
    await expect(page.getByRole('log')).toContainText('is the midpoint of the mean and the median');
    await expect(box(page)).toHaveValue('');
    await expect(page.getByRole('button', { name: 'Try again' })).toHaveCount(0);
  });

  test('a project that is gone offers to ask without it', async ({ page }) => {
    await mockApp(page, (route) => (route.request().postDataJSON().project_id ? refused(404)(route) : streamed(route)));
    await mockProject(page);
    await openPanel(page, `/projects/${PROJECT_ID}`);
    await expect(page.getByRole('dialog', { name: 'Assistant' })).toHaveAccessibleDescription('Project “Flood prevention”');

    await ask(page);
    await expect(page.getByText('This project is not available.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Open projects' })).toHaveAttribute('href', '/projects');
    await expect(box(page)).toHaveValue(QUESTION);

    await page.getByRole('button', { name: 'Ask without the project' }).click();
    await expect(page.getByRole('dialog', { name: 'Assistant' })).toHaveAccessibleDescription('Method and app');

    const general = page.waitForRequest(STREAM);
    await box(page).press('Enter');

    expect((await general).postDataJSON()).toMatchObject({ message: QUESTION, project_id: null });
    await expect(page.getByRole('log')).toContainText('is the midpoint of the mean and the median');
  });

  test('a stream that breaks keeps the text it delivered and offers to ask again', async ({ page }) => {
    let calls = 0;
    await mockApp(page, (route) =>
      ++calls === 1
        ? route.fulfill({
            status: 200,
            contentType: 'text/event-stream',
            body: sse([['token', { text: 'The best compromise is' }]]),
          })
        : streamed(route)
    );
    await openPanel(page);

    await ask(page);
    await expect(page.getByText('The connection dropped before the answer finished.')).toBeVisible();
    await expect(page.getByRole('log')).toContainText('The best compromise is');

    const retried = page.waitForRequest(STREAM);
    await page.getByRole('button', { name: 'Try again' }).click();

    expect(questionOf(await retried)).toBe(QUESTION);
    await expect(page.getByRole('log')).toContainText('is the midpoint of the mean and the median');
  });

  for (const theme of ['light', 'dark'] as const) {
    test(`the clear confirmation passes the WCAG audit in the ${theme} theme`, async ({ page }) => {
      await page.addInitScript((value) => localStorage.setItem('become-theme', value), theme);
      await mockApp(page, streamed);
      await openPanel(page);
      await ask(page);
      await expect(page.getByRole('log')).toContainText('is the midpoint');
      await page.getByRole('button', { name: 'Clear conversation' }).click();
      await expect(page.getByRole('group', { name: 'Clear the conversation? This cannot be undone.' })).toBeVisible();
      await expect(page.locator('html')).toHaveClass(new RegExp(theme));

      expect(await auditDialog(page)).toEqual([]);
    });
  }

  test('clearing asks first and then empties the conversation', async ({ page }) => {
    await mockApp(page, streamed);
    await openPanel(page);
    await ask(page);
    await expect(page.getByRole('log')).toContainText('is the midpoint');

    await page.getByRole('button', { name: 'Clear conversation' }).click();
    await expect(page.getByRole('group', { name: 'Clear the conversation? This cannot be undone.' })).toBeVisible();
    await page.getByRole('button', { name: 'Keep' }).click();
    await expect(page.getByRole('log')).toContainText('is the midpoint');

    await page.getByRole('button', { name: 'Clear conversation' }).click();
    await page.getByRole('button', { name: 'Clear', exact: true }).click();

    await expect(page.getByRole('log')).toHaveCount(0);
    await expect(page.getByText('Ask about the method or the app')).toBeVisible();
  });
});
