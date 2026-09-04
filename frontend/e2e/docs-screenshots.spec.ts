import { test as base, expect, Page } from '@playwright/test';

import { registerUser, uniqueId } from './helpers';

/**
 * Screenshots for the documentation site, written to `docs/user/img/`.
 *
 * Deliberately separate from `visual-regression.spec.ts`, which looks similar and is
 * not the same thing. Those snapshots are byte-compared baselines: they exist to fail
 * when a pixel moves, they are rendered on Linux in CI, and they cannot be regenerated
 * on an arm64 Mac. These are illustrations. Nothing compares them, a Mac render is
 * fine, and the only test they have to pass is a person looking at the page.
 *
 * Tying the two together would make the documentation dictate what the regression
 * suite checks, so they stay apart even though they photograph the same screens.
 *
 * Every shot comes from the example project that seeding gives a fresh account, so the
 * pictures show the flood-prevention panel the user guide describes, and no real
 * account or real panel appears in public documentation.
 *
 * Run it with the stack up:
 *
 *     ./scripts/ci/e2e-local.sh docs
 */

const IMG = '../docs/user/img';

// `reducedMotion` matters more here than it looks. The project page animates its
// heading and description in on scroll, so a screenshot taken before that finishes
// catches them mid-fade and the picture ships with a washed-out title.
const test = base.extend<{ page: Page }>({
  page: async ({ browser }, use) => {
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'en');
      localStorage.setItem('become-theme', 'light');
    });
    await use(page);
    await context.close();
  },
});

const EXAMPLE = 'Flood Prevention Planning';

// Sign-in raises a "Welcome back!" toast, and shadcn's remove delay is about sixteen
// minutes, so it does not go away on its own. Left up, it sits over the chart in every
// picture taken afterwards.
async function dismissToasts(page: Page) {
  const close = page.locator('[toast-close]');
  for (let i = 0; i < 3 && (await close.count()) > 0; i += 1) {
    await close.first().click().catch(() => undefined);
    await page.waitForTimeout(200);
  }
}

// Wait for every fade to finish before the shutter opens.
//
// `reducedMotion: 'reduce'` is set on the context above and it is NOT enough: it stops
// CSS transitions, but framer-motion drives these with inline styles and animates a
// card in when it scrolls into view. A screenshot taken a moment too early catches the
// card at partial opacity, and the picture ships looking like a half-loaded page. That
// is exactly what happened to the first set, and it survived review because the shots
// were checked by eye rather than measured.
//
// framer-motion writes `style="opacity: 0.42"` while it works and leaves a clean 0 or 1
// when it is done, so anything strictly between the two means something is still moving.
async function settled(page: Page) {
  await page.waitForFunction(
    () => {
      const moving = [...document.querySelectorAll<HTMLElement>('[style*="opacity"]')];
      return moving.every((el) => {
        const o = parseFloat(el.style.opacity);
        return Number.isNaN(o) || o === 0 || o === 1;
      });
    },
    undefined,
    { timeout: 10000 },
  );
  // Chromium can present a frame after the style settles, so give it one.
  await page.waitForTimeout(150);
}

async function openExampleProject(page: Page) {
  await page.getByRole('link', { name: EXAMPLE }).click();
  await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });
  await expect(page.getByRole('heading', { name: EXAMPLE })).toBeVisible();
}

test.describe('documentation screenshots', () => {
  test('projects list, example project, and results', async ({ page }) => {
    await registerUser(page, `docs-${uniqueId()}@test.com`, 'Alex', 'Novak');

    await expect(page.getByRole('link', { name: EXAMPLE })).toBeVisible({
      timeout: 10000,
    });
    await dismissToasts(page);
    await settled(page);
    // The card is the element that actually went out washed out, so it gets its own
    // check rather than trusting the general one. `settled` only sees inline opacity;
    // a fade driven by a CSS class would slip past it.
    await expect(page.getByRole('link', { name: EXAMPLE })).toHaveCSS('opacity', '1');
    // `main` rather than the window: a fresh account owns one project, so a viewport
    // shot is a small card in the corner of a large white rectangle.
    await page.getByRole('main').screenshot({ path: `${IMG}/projects-list.png` });

    await openExampleProject(page);
    await dismissToasts(page);
    await settled(page);
    await page.screenshot({ path: `${IMG}/project-opinions.png` });

    // There is no "Results" tab. The result sits in the same column below the
    // opinions, and the only tablist on the page is the visualization's
    // Landscape / Triangle / Centroid. Reading the rendered page said otherwise,
    // because those three words are section headings in the text.
    const result = page.getByRole('heading', { name: /Best Compromise/ });
    await expect(result).toBeVisible({ timeout: 15000 });
    await result.scrollIntoViewIfNeeded();
    await settled(page);

    // The card, not the window. At this width the layout is two columns and the result
    // panel already sits beside the opinion form, so a viewport shot here produced a
    // file identical to the one above under a different name. Two names for one picture
    // is worse than one picture, because the page around it claims they differ.
    // Two levels: the title sits in a header inside the card. Three went past the card
    // and swallowed the chart as well, which showed up as `14.31` matching in three
    // places at once, one of them a label inside the SVG.
    const resultCard = result.locator('../..');
    // Bounded from both sides. The first says the card holds the number the caption
    // promises; the second says the frame stopped at the card, because an ancestor that
    // is too high still screenshots happily and just quietly includes the neighbours.
    await expect(resultCard.getByText('14.31', { exact: true })).toBeVisible();
    await expect(resultCard.getByTestId('landscape-best-label')).toHaveCount(0);
    await resultCard.screenshot({ path: `${IMG}/project-results.png` });

    const triangleTab = page.getByRole('tab', { name: 'Triangle' });
    await triangleTab.click();
    await expect(triangleTab).toHaveAttribute('aria-selected', 'true');
    await dismissToasts(page);
    await page.waitForTimeout(600);

    // The card rather than the window: a viewport shot cuts the chart off at the fold,
    // and the guide points at the legend, which is the part that gets cut. Two levels
    // up, because the title sits in a header inside the card; one level produced a
    // 2.5 KB strip of the heading and nothing else, and it produced it silently.
    const viz = page.getByRole('heading', { name: 'Visualization' }).locator('../..');
    // Assert the frame actually holds the chart. A wrong ancestor still screenshots
    // happily, and a picture of the wrong element is the kind of mistake that ships.
    await expect(viz.getByRole('tab', { name: 'Triangle' })).toBeVisible();
    await viz.scrollIntoViewIfNeeded();
    await settled(page);
    await viz.screenshot({ path: `${IMG}/project-triangle.png` });

    // The same chart with every opinion drawn. Both user pages tell the reader this is
    // what separates "one group with spread" from "two camps with a gap", and on the
    // flood panel it is the picture that carries the argument: the aggregate curves sit
    // low and tight while the individual triangles stand in two clusters far apart.
    const individual = viz.getByRole('checkbox', { name: /individual opinions/i });
    await individual.click();
    await expect(individual).toBeChecked();
    await settled(page);
    await viz.screenshot({ path: `${IMG}/project-triangle-individual.png` });

    // The guide says "the chart" and there are three of them. Landscape is the default
    // view and Centroid collapses each opinion to one point, which is the view that
    // shows the gap between the camps as a gap rather than as overlapping triangles.
    for (const view of ['Landscape', 'Centroid'] as const) {
      const tab = page.getByRole('tab', { name: view });
      await tab.click();
      await expect(tab).toHaveAttribute('aria-selected', 'true');
      await settled(page);
      await viz.screenshot({ path: `${IMG}/project-${view.toLowerCase()}.png` });
    }

    // The arithmetic the worked example walks through, as the app shows it.
    const calcs = page.getByRole('button', { name: /supporting calculations/i });
    await calcs.scrollIntoViewIfNeeded();
    await calcs.click();
    const calcsCard = calcs.locator('..');
    // Both directions, and this one earned the lesson twice: the first attempt used two
    // levels, asserted only that the mean was inside, passed, and photographed the nav
    // bar, the result card and the whole chart along with it. "Something is inside" does
    // not bound a frame. Say what must be outside as well.
    await expect(calcsCard.getByText(/arithmetic mean/i).first()).toBeVisible();
    await expect(calcsCard.getByRole('heading', { name: 'Visualization' })).toHaveCount(0);
    await expect(calcsCard.getByRole('navigation')).toHaveCount(0);
    await settled(page);
    await calcsCard.screenshot({ path: `${IMG}/project-supporting-calculations.png` });
  });

  // Cannot pass until a Likert project can be created at all. The scale becomes Likert
  // when the unit is EMPTY, and `CreateProjectModal.tsx` requires a non-empty one, so the
  // dialog never closes and the test dies there. The backend accepts an empty unit and the
  // verdict logic is written and tested; only the form stands in the way. Tracked as
  // BCM-67. Unskip this the moment that validation is relaxed, because the picture it
  // takes is the one the guide is missing.
  test.fixme('a Likert project reports a verdict', async ({ page }) => {
    await registerUser(page, `docs-lk-${uniqueId()}@test.com`, 'Alex', 'Novak');
    await dismissToasts(page);

    // 0 to 100 with the unit left blank is what makes a scale Likert. The dialog
    // already defaults to that range, so the empty unit is the whole trick, and it is
    // the thing the guide warns is easy to get wrong.
    await page.getByRole('button', { name: /new project/i }).first().click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder('Enter project name').fill('Adopt the new policy');
    await dialog.getByRole('button', { name: 'Create Project' }).click();
    await expect(dialog).toBeHidden({ timeout: 10000 });

    await page.getByRole('link', { name: 'Adopt the new policy' }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

    await page.getByLabel('Position').first().fill('Head of Department');
    await page.getByLabel('Lower (pessimistic)').first().fill('60');
    await page.getByLabel('Peak (most likely)').first().fill('75');
    await page.getByLabel('Upper (optimistic)').first().fill('90');
    await page.getByRole('button', { name: 'Save Opinion' }).click();

    const verdict = page.getByRole('heading', { name: /Best Compromise/ });
    await expect(verdict).toBeVisible({ timeout: 15000 });
    await dismissToasts(page);
    const verdictCard = verdict.locator('../..');
    // The point of the picture: words, not a decimal. Assert one of the five positions
    // is on screen, so a project that silently came out numeric fails here rather than
    // shipping a screenshot that contradicts the page it illustrates.
    await expect(
      verdictCard.getByText(/strongly agree|rather agree|neutral|rather disagree|strongly disagree/i).first(),
    ).toBeVisible();
    await settled(page);
    await verdictCard.screenshot({ path: `${IMG}/project-likert-verdict.png` });
  });

  test('the new project dialog', async ({ page }) => {
    await registerUser(page, `docs-np-${uniqueId()}@test.com`, 'Alex', 'Novak');
    await dismissToasts(page);

    await page.getByRole('button', { name: /new project/i }).first().click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder('Enter project name').fill('Budget allocation 2027');
    await dialog.getByLabel('Unit').fill('CZK billions');
    await settled(page);
    await page.screenshot({ path: `${IMG}/new-project.png` });
  });
});
