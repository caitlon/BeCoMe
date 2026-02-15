import { test, expect, Page, BrowserContext } from '@playwright/test';
import { uniqueId, TEST_PASSWORD, registerUser } from './helpers';

const NEW_PASSWORD = 'NewSecurePass99!';

test.describe.serial('Profile Page Flow', () => {
  let page: Page;
  let context: BrowserContext;
  const testEmail = `profile-${uniqueId()}@test.com`;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext();
    page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'en');
    });
  });

  test.afterAll(async () => {
    await page.close();
    await context.close();
  });

  test('register and navigate to profile', async () => {
    await registerUser(page, testEmail, 'Original', 'Name');

    // Navigate to profile via URL
    await page.goto('/profile');
    await expect(page.getByRole('heading', { name: 'Original Name' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(testEmail)).toBeVisible();
  });

  test('update first and last name', async () => {
    const firstNameInput = page.getByLabel('First Name');
    const lastNameInput = page.getByLabel('Last Name');

    await firstNameInput.clear();
    await firstNameInput.fill('Updated');

    await lastNameInput.clear();
    await lastNameInput.fill('Person');

    await page.getByRole('button', { name: 'Save Changes' }).click();

    // Toast confirms update
    await expect(page.getByText('Profile updated', { exact: true }).first()).toBeVisible({ timeout: 5000 });

    // Name should reflect in the heading
    await expect(page.getByRole('heading', { name: 'Updated Person' })).toBeVisible({ timeout: 5000 });
  });

  test('change password', async () => {
    await page.getByLabel('Current Password').fill(TEST_PASSWORD);
    await page.getByLabel('New Password', { exact: true }).fill(NEW_PASSWORD);
    await page.getByLabel('Confirm New Password').fill(NEW_PASSWORD);

    await page.getByRole('button', { name: 'Update Password' }).click();

    // Toast confirms password change
    await expect(page.getByText('Password updated', { exact: true }).first()).toBeVisible({ timeout: 5000 });
  });

  test('delete account redirects to home', async () => {
    // Click delete button in Danger Zone
    await page.getByRole('button', { name: 'Delete Account' }).click();

    // Confirmation modal appears
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Delete Account?')).toBeVisible();

    // Confirm deletion
    await dialog.getByRole('button', { name: 'Delete My Account' }).click();

    // Redirected to login page after account deletion
    await expect(page).toHaveURL('/login', { timeout: 10000 });
  });
});
