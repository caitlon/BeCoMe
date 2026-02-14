import { test, expect } from './fixtures/base';

test.describe('Navigation', () => {
  test('navbar links navigate to correct pages', async ({ page }) => {
    await page.goto('/');

    const nav = page.getByRole('navigation');

    await nav.getByRole('link', { name: /^About$/i }).click();
    await expect(page).toHaveURL('/about');

    await nav.getByRole('link', { name: /^Docs$/i }).click();
    await expect(page).toHaveURL('/docs');

    await nav.getByRole('link', { name: /^FAQ$/i }).click();
    await expect(page).toHaveURL('/faq');

    await nav.getByRole('link', { name: /Case Studies/i }).click();
    await expect(page).toHaveURL('/case-studies');
  });

  test('protected route redirects to login', async ({ page }) => {
    await page.goto('/projects');

    await expect(page).toHaveURL('/login');
    await expect(
      page.getByRole('heading', { name: /Welcome Back/i, level: 1 })
    ).toBeVisible();
  });

  test('footer links navigate correctly', async ({ page }) => {
    await page.goto('/');

    const footer = page.locator('footer');

    await footer.getByRole('link', { name: /^About$/i }).click();
    await expect(page).toHaveURL('/about');

    await page.goto('/');

    await footer.getByRole('link', { name: /Documentation/i }).click();
    await expect(page).toHaveURL('/docs');
  });
});
