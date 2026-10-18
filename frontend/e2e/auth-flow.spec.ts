import { test, expect } from './fixtures/base';
import { registerUser, uniqueId } from './helpers';

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

  test('sign-in and registration pages follow the session', async ({ page }) => {
    const navigation = page.getByRole('navigation', { name: 'Main navigation' });
    await registerUser(page, `guest-route-${uniqueId()}@test.com`, 'Guest', 'Route');

    await page.goto('/login');
    await expect(page).toHaveURL('/projects');

    await page.goto('/register');
    await expect(page).toHaveURL('/projects');

    // Sign-out reloads `/`, and that page runs its own session probe; catch its refusal so it
    // cannot be mistaken for the one on the sign-in page below.
    const homeProbed = page.waitForResponse(
      (r) => r.url().includes('/api/v1/auth/refresh') && r.status() === 401
    );
    await navigation.getByRole('button', { name: /Guest Route/ }).click();
    await page.getByRole('menuitem', { name: 'Sign Out' }).click();
    await expect(page).toHaveURL('/');
    await homeProbed;

    // GuestRoute renders the page while auth is loading, so wait for this page's anonymous probe
    // to be refused before judging it.
    const loginProbed = page.waitForResponse(
      (r) => r.url().includes('/api/v1/auth/refresh') && r.status() === 401
    );
    await page.goto('/login');
    await loginProbed;
    await expect(page).toHaveURL('/login');
    await expect(
      page.getByRole('heading', { name: /Welcome Back/i, level: 1 })
    ).toBeVisible();
    await expect(navigation).not.toContainText('Guest Route');

    // Same wait as above: this page's anonymous probe must be refused before the page is judged.
    const registerProbed = page.waitForResponse(
      (r) => r.url().includes('/api/v1/auth/refresh') && r.status() === 401
    );
    await page.goto('/register');
    await registerProbed;
    await expect(page).toHaveURL('/register');
    await expect(
      page.getByRole('heading', { name: /Create Account/i, level: 1 })
    ).toBeVisible();
    await expect(navigation).not.toContainText('Guest Route');
  });
});
