import { test, expect } from './fixtures/base';
import {
  TEST_PASSWORD,
  activationLinkFor,
  signIn,
  submitRegistration,
  uniqueId,
} from './helpers';

test.describe('Email verification', () => {
  test('registration acknowledges the mail and opens no session', async ({ page }) => {
    const email = `verify-none-${uniqueId()}@test.com`;

    await submitRegistration(page, email);

    // The address is repeated back, so a typo is visible before anyone waits on mail.
    await expect(page.getByText(email)).toBeVisible();

    // Nothing was signed in, so the application's own pages stay closed.
    await page.goto('/projects');
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });

  test('an account whose address is unconfirmed cannot sign in', async ({ page }) => {
    const email = `verify-gate-${uniqueId()}@test.com`;
    await submitRegistration(page, email);

    await page.goto('/login');
    await page.getByPlaceholder('you@example.com').fill(email);
    await page.getByPlaceholder('Enter your password').fill(TEST_PASSWORD);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(
      page.getByRole('heading', { name: 'Confirm your email to continue', level: 1 })
    ).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test('the emailed link refuses a wrong password and activates on the right one', async ({
    page,
  }) => {
    const email = `verify-link-${uniqueId()}@test.com`;
    await submitRegistration(page, email);

    const link = new URL(await activationLinkFor(email));
    await page.goto(`${link.pathname}${link.search}`);

    // Whoever holds the link still has to know the password the submission carried.
    // This is the whole reason a stranger cannot activate an account for someone else.
    await page.getByPlaceholder('Enter your password').fill('NotThePassword1!');
    await page.getByRole('button', { name: 'Confirm email' }).click();

    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/\/verify-email/);

    // The link survives the refusal and the form stays usable, so the owner can just
    // correct the typo.
    await page.getByPlaceholder('Enter your password').fill(TEST_PASSWORD);
    await page.getByRole('button', { name: 'Confirm email' }).click();
    await expect(page).toHaveURL('/login', { timeout: 15000 });

    // That mismatch also spent from the login counter. Signing in immediately after is
    // what proves activation clears it, instead of confirming the address and then
    // refusing the owner entry to the account they just opened.
    await signIn(page, email);
  });
});
