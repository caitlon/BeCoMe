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
    await page.screenshot({ path: `${IMG}/projects-list.png` });

    await openExampleProject(page);
    await dismissToasts(page);
    await page.screenshot({ path: `${IMG}/project-opinions.png` });

    // There is no "Results" tab. The result sits in the same column below the
    // opinions, and the only tablist on the page is the visualization's
    // Landscape / Triangle / Centroid. Reading the rendered page said otherwise,
    // because those three words are section headings in the text.
    const result = page.getByRole('heading', { name: /Best Compromise/ });
    await expect(result).toBeVisible({ timeout: 15000 });
    await result.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${IMG}/project-results.png` });

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
    await viz.screenshot({ path: `${IMG}/project-triangle.png` });

    // The same chart with every opinion drawn. Both user pages tell the reader this is
    // what separates "one group with spread" from "two camps with a gap", and on the
    // flood panel it is the picture that carries the argument: the aggregate curves sit
    // low and tight while the individual triangles stand in two clusters far apart.
    const individual = viz.getByRole('checkbox', { name: /individual opinions/i });
    await individual.click();
    await expect(individual).toBeChecked();
    await page.waitForTimeout(700);
    await viz.screenshot({ path: `${IMG}/project-triangle-individual.png` });
  });

  test('the new project dialog', async ({ page }) => {
    await registerUser(page, `docs-np-${uniqueId()}@test.com`, 'Alex', 'Novak');
    await dismissToasts(page);

    await page.getByRole('button', { name: /new project/i }).first().click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder('Enter project name').fill('Budget allocation 2027');
    await dialog.getByLabel('Unit').fill('CZK billions');
    await page.screenshot({ path: `${IMG}/new-project.png` });
  });
});
