import { test, expect } from './fixtures/base';

test.describe('Public Pages', () => {
  test('landing page loads and shows hero', async ({ page }) => {
    await page.goto('/');

    await expect(
      page.getByRole('heading', { level: 1 })
    ).toContainText('Group Decisions,');

    await expect(
      page.getByRole('link', { name: /Start Your Project/i })
    ).toBeVisible();

    await expect(
      page.getByRole('heading', { name: /How It Works/i })
    ).toBeVisible();
  });

  test('about page loads', async ({ page }) => {
    await page.goto('/about');

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.locator('main#main-content')).toBeVisible();
  });

  test('documentation page loads', async ({ page }) => {
    await page.goto('/docs');

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.locator('main#main-content')).toBeVisible();
  });

  test('FAQ page loads', async ({ page }) => {
    await page.goto('/faq');

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.locator('main#main-content')).toBeVisible();
  });

  test('case studies page loads', async ({ page }) => {
    await page.goto('/case-studies');

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { level: 3 }).first()).toBeVisible();
  });

  test('404 page shows for invalid route', async ({ page }) => {
    await page.goto('/this-route-does-not-exist');

    await expect(
      page.getByRole('heading', { name: '404', level: 1 })
    ).toBeVisible();

    await expect(
      page.getByRole('link', { name: /Back to Home/i })
    ).toBeVisible();
  });
});
