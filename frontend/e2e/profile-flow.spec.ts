import { test, expect, Page } from '@playwright/test';

const uniqueId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const TEST_PASSWORD = 'TestPass123!@#';
const NEW_PASSWORD = 'NewSecurePass99!';

async function registerUser(page: Page, email: string, firstName: string, lastName: string) {
  await page.goto('/register');

  const emailField = page.getByPlaceholder('you@example.com');
  await emailField.fill(email);
  await emailField.blur();

  const passwordField = page.getByPlaceholder('Min. 12 characters');
  await passwordField.fill(TEST_PASSWORD);
  await passwordField.blur();

  const confirmField = page.getByPlaceholder('Confirm your password');
  await confirmField.fill(TEST_PASSWORD);
  await confirmField.blur();

  const firstNameField = page.getByPlaceholder('John');
  await firstNameField.fill(firstName);
  await firstNameField.blur();

  const lastNameField = page.getByPlaceholder('Doe');
  await lastNameField.fill(lastName);
  await lastNameField.blur();

  const submitBtn = page.getByRole('button', { name: 'Create Account' });
  await expect(submitBtn).toBeEnabled({ timeout: 10000 });
  await submitBtn.click();

  await expect(page).toHaveURL('/projects', { timeout: 10000 });
}

test.describe.serial('Profile Page Flow', () => {
  let page: Page;
  const testEmail = `profile-${uniqueId()}@test.com`;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'en');
    });
  });

  test.afterAll(async () => {
    await page.close();
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
