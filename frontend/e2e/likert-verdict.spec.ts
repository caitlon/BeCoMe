import { test, expect } from '@playwright/test';

import { registerUser, uniqueId } from './helpers';

/**
 * A project on the 0-100 scale with no unit is a Likert agreement project: its result
 * reads as a position in words, with a recommendation, next to the number. The path
 * crosses three layers that each broke on their own once: the form refused an empty
 * unit, the API dropped the recommendation, and no component rendered the verdict.
 */
test.describe('Likert agreement verdict', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'en');
    });
  });

  test('a project with the unit left empty shows the verdict on its result', async ({ page }) => {
    await registerUser(page, `likert-${uniqueId()}@test.com`, 'Alex', 'Novak');

    const projectName = `Likert ${uniqueId()}`;
    await page.getByRole('button', { name: /new project/i }).first().click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder('Enter project name').fill(projectName);
    // The dialog opens on 0 to 100. The unit stays empty, and that is the whole point.
    await expect(dialog.getByPlaceholder('Min')).toHaveValue('0');
    await expect(dialog.getByPlaceholder('Max')).toHaveValue('100');
    await expect(dialog.getByLabel('Unit')).toHaveValue('');
    await dialog.getByRole('button', { name: 'Create Project' }).click();
    await expect(dialog).toBeHidden({ timeout: 10000 });

    await page.getByRole('link', { name: projectName }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

    // One expert at (60, 75, 90): every aggregate equals the input, so the compromise
    // centroid is exactly 75, the "Rather agree" position.
    await page.getByLabel('Position').first().fill('Head of Department');
    await page.getByLabel('Lower (pessimistic)').first().fill('60');
    await page.getByLabel('Peak (most likely)').first().fill('75');
    await page.getByLabel('Upper (optimistic)').first().fill('90');
    await page.getByRole('button', { name: 'Save Opinion' }).click();

    await expect(page.getByRole('heading', { name: /Best Compromise/ })).toBeVisible({
      timeout: 15000,
    });
    const verdict = page.getByRole('region', { name: 'Agreement verdict' });
    await expect(verdict).toBeVisible();
    await expect(verdict.getByText('Rather agree', { exact: true })).toBeVisible();
    await expect(
      verdict.getByText('Policy is recommended with minor adjustments', { exact: true }),
    ).toBeVisible();
  });

  test('a project with a unit shows no verdict', async ({ page }) => {
    await registerUser(page, `likert-unit-${uniqueId()}@test.com`, 'Alex', 'Novak');

    const projectName = `Unit ${uniqueId()}`;
    await page.getByRole('button', { name: /new project/i }).first().click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder('Enter project name').fill(projectName);
    await dialog.getByLabel('Unit').fill('%');
    await dialog.getByRole('button', { name: 'Create Project' }).click();
    await expect(dialog).toBeHidden({ timeout: 10000 });

    await page.getByRole('link', { name: projectName }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

    await page.getByLabel('Position').first().fill('Head of Department');
    await page.getByLabel('Lower (pessimistic)').first().fill('60');
    await page.getByLabel('Peak (most likely)').first().fill('75');
    await page.getByLabel('Upper (optimistic)').first().fill('90');
    await page.getByRole('button', { name: 'Save Opinion' }).click();

    await expect(page.getByRole('heading', { name: /Best Compromise/ })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByRole('region', { name: 'Agreement verdict' })).toHaveCount(0);
  });
});
