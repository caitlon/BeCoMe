import { test as base, expect, Page } from '@playwright/test';

import { registerUser, uniqueId } from './helpers';

/**
 * Create a test fixture that sets theme and disables animations.
 * reducedMotion: 'reduce' disables FuzzyTriangleSVG interval animation,
 * Recharts scatter animation, and framer-motion transitions.
 */
function createThemeTest(theme: 'light' | 'dark') {
  return base.extend({
    page: async ({ browser }, use) => {
      const context = await browser.newContext({
        reducedMotion: 'reduce',
      });
      const page = await context.newPage();
      await page.addInitScript((t: string) => {
        localStorage.setItem('become-language', 'en');
        localStorage.setItem('vite-ui-theme', t);
      }, theme);
      await use(page);
      await context.close();
    },
  });
}

const lightTest = createThemeTest('light');
const darkTest = createThemeTest('dark');

async function createProjectWithOpinion(page: Page) {
  const projectName = `VR Project ${Date.now()}`;
  await page.getByRole('button', { name: 'Create Your First Project' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();

  await dialog.getByPlaceholder('Enter project name').fill(projectName);
  await dialog.getByLabel('Unit').fill('%');
  await dialog.getByRole('button', { name: 'Create Project' }).click();
  await expect(dialog).toBeHidden({ timeout: 10000 });

  await page.getByRole('link', { name: projectName }).click();
  await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

  await page.getByLabel('Position').first().fill('VR Expert');
  await page.getByLabel('Lower (pessimistic)').first().fill('30');
  await page.getByLabel('Peak (most likely)').first().fill('50');
  await page.getByLabel('Upper (optimistic)').first().fill('70');

  await page.getByRole('button', { name: 'Save Opinion' }).click();
  await expect(page.getByText('Opinion saved', { exact: true })).toBeVisible({
    timeout: 5000,
  });

  await expect(page.getByRole('heading', { name: /Best Compromise/ })).toBeVisible({
    timeout: 10000,
  });
}

// --- Light Theme ---

lightTest.describe('Visual Regression — Light Theme', () => {
  lightTest('landing page hero', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const svg = page.locator('svg[role="img"]').first();
    await expect(svg).toBeVisible();

    await expect(page).toHaveScreenshot('landing-hero-light.png');
  });

  lightTest('case study budget page', async ({ page }) => {
    await page.goto('/case-study/budget');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading').first()).toBeVisible();

    await expect(page).toHaveScreenshot('case-study-budget-light.png', {
      fullPage: true,
    });
  });

  lightTest('project results — triangle visualization', async ({ page }) => {
    const email = `vr-tri-light-${uniqueId()}@test.com`;
    await registerUser(page, email, 'VR', 'Light');
    await createProjectWithOpinion(page);

    const triangleTab = page.getByRole('tab', { name: /triangle/i });
    await expect(triangleTab).toHaveAttribute('aria-selected', 'true');

    await expect(page).toHaveScreenshot('project-results-triangle-light.png');
  });

  lightTest('project results — centroid chart', async ({ page }) => {
    const email = `vr-cen-light-${uniqueId()}@test.com`;
    await registerUser(page, email, 'VR', 'Centroid');
    await createProjectWithOpinion(page);

    const centroidTab = page.getByRole('tab', { name: /centroid/i });
    await centroidTab.click();
    await expect(centroidTab).toHaveAttribute('aria-selected', 'true');

    // Wait for Recharts scatter plot to render
    await expect(page.locator('.recharts-scatter')).toBeVisible({ timeout: 5000 });

    await expect(page).toHaveScreenshot('project-results-centroid-light.png');
  });
});

// --- Dark Theme ---

darkTest.describe('Visual Regression — Dark Theme', () => {
  darkTest('landing page hero', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const svg = page.locator('svg[role="img"]').first();
    await expect(svg).toBeVisible();

    await expect(page).toHaveScreenshot('landing-hero-dark.png');
  });

  darkTest('case study budget page', async ({ page }) => {
    await page.goto('/case-study/budget');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading').first()).toBeVisible();

    await expect(page).toHaveScreenshot('case-study-budget-dark.png', {
      fullPage: true,
    });
  });

  darkTest('project results — triangle visualization', async ({ page }) => {
    const email = `vr-tri-dark-${uniqueId()}@test.com`;
    await registerUser(page, email, 'VR', 'Dark');
    await createProjectWithOpinion(page);

    const triangleTab = page.getByRole('tab', { name: /triangle/i });
    await expect(triangleTab).toHaveAttribute('aria-selected', 'true');

    await expect(page).toHaveScreenshot('project-results-triangle-dark.png');
  });

  darkTest('project results — centroid chart', async ({ page }) => {
    const email = `vr-cen-dark-${uniqueId()}@test.com`;
    await registerUser(page, email, 'VR', 'CenDark');
    await createProjectWithOpinion(page);

    const centroidTab = page.getByRole('tab', { name: /centroid/i });
    await centroidTab.click();
    await expect(centroidTab).toHaveAttribute('aria-selected', 'true');

    await expect(page.locator('.recharts-scatter')).toBeVisible({ timeout: 5000 });

    await expect(page).toHaveScreenshot('project-results-centroid-dark.png');
  });
});
