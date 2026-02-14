import { test, expect } from './fixtures/base';

test.describe('Authentication Flows', () => {
  test('login page renders form with all fields', async ({ page }) => {
    await page.goto('/login');

    await expect(
      page.getByRole('heading', { name: /Welcome Back/i, level: 1 })
    ).toBeVisible();

    await expect(page.getByLabel(/^Email$/i)).toBeVisible();
    await expect(page.getByLabel(/^Password$/i)).toBeVisible();
    await expect(
      page.getByRole('button', { name: /Sign In/i })
    ).toBeVisible();
  });

  test('register page renders form with all fields', async ({ page }) => {
    await page.goto('/register');

    await expect(
      page.getByRole('heading', { name: /Create Account/i, level: 1 })
    ).toBeVisible();

    await expect(page.getByLabel(/Email/i)).toBeVisible();
    await expect(page.getByLabel(/First Name/i)).toBeVisible();
    await expect(
      page.getByRole('button', { name: /Create Account/i })
    ).toBeVisible();
  });

  test('login page has link to register', async ({ page }) => {
    await page.goto('/login');

    const registerLink = page.getByRole('link', { name: /Create one/i });
    await expect(registerLink).toBeVisible();

    await registerLink.click();
    await expect(page).toHaveURL('/register');
  });

  test('login form stays visible on empty submit', async ({ page }) => {
    await page.goto('/login');

    await page.getByRole('button', { name: /Sign In/i }).click();

    // Form should remain visible (HTML5 validation prevents submission)
    await expect(
      page.getByRole('heading', { name: /Welcome Back/i, level: 1 })
    ).toBeVisible();
    await expect(page.getByLabel(/^Email$/i)).toBeVisible();
  });
});
