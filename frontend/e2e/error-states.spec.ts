import { Page } from '@playwright/test';
import { test, expect } from './fixtures/base';

const uniqueId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const TEST_PASSWORD = 'TestPass123!@#';

async function registerAndLogin(page: Page, email: string, firstName: string, lastName: string) {
  await page.goto('/register');
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('you@example.com').blur();
  await page.getByPlaceholder('Min. 12 characters').fill(TEST_PASSWORD);
  await page.getByPlaceholder('Min. 12 characters').blur();
  await page.getByPlaceholder('Confirm your password').fill(TEST_PASSWORD);
  await page.getByPlaceholder('Confirm your password').blur();
  await page.getByPlaceholder('John').fill(firstName);
  await page.getByPlaceholder('John').blur();
  await page.getByPlaceholder('Doe').fill(lastName);
  await page.getByPlaceholder('Doe').blur();

  const registerBtn = page.getByRole('button', { name: 'Create Account' });
  await expect(registerBtn).toBeEnabled({ timeout: 10000 });
  await registerBtn.click();
  await expect(page).toHaveURL('/projects', { timeout: 10000 });
}

test.describe('Error States', () => {
  test('shows validation error for invalid fuzzy number', async ({ page }) => {
    const email = `err-fuzzy-${uniqueId()}@test.com`;
    await registerAndLogin(page, email, 'Error', 'Tester');

    // Create a project
    await page.getByRole('button', { name: 'Create Your First Project' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder('Enter project name').fill(`Error Test ${Date.now()}`);
    await dialog.getByLabel('Unit').fill('%');
    await dialog.getByRole('button', { name: 'Create Project' }).click();
    await expect(dialog).toBeHidden({ timeout: 10000 });

    // Navigate to the project
    await page.getByRole('link').filter({ hasText: 'Error Test' }).first().click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Fill opinion with invalid values: lower > peak
    await page.getByLabel('Position').first().fill('Tester');
    await page.getByLabel('Lower (pessimistic)').first().fill('80');
    await page.getByLabel('Peak (most likely)').first().fill('50');
    await page.getByLabel('Upper (optimistic)').first().fill('90');

    await page.getByRole('button', { name: 'Save Opinion' }).click();

    // Validation error should appear as a toast
    await expect(page.getByText(/lower ≤ peak ≤ upper/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('shows error for empty project name', async ({ page }) => {
    const email = `err-name-${uniqueId()}@test.com`;
    await registerAndLogin(page, email, 'Empty', 'Name');

    // Open create project dialog
    await page.getByRole('button', { name: 'Create Your First Project' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Fill unit but leave name empty, then try to submit
    await dialog.getByLabel('Unit').fill('%');
    await dialog.getByRole('button', { name: 'Create Project' }).click();

    // Dialog should remain open (validation prevents submission)
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/required/i)).toBeVisible({ timeout: 5000 });
  });

  test('shows validation errors for weak password', async ({ page }) => {
    await page.goto('/register');

    // Enter a weak password (too short, no special chars)
    const passwordField = page.getByPlaceholder('Min. 12 characters');
    await passwordField.fill('weak');
    await passwordField.blur();

    // Validation indicators should show requirements not met
    await expect(page.getByText(/12 characters/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('redirects to login on expired session', async ({ page }) => {
    const email = `err-session-${uniqueId()}@test.com`;
    await registerAndLogin(page, email, 'Session', 'Test');

    // Clear auth tokens from localStorage (simulate expired session)
    await page.evaluate(() => {
      const lang = localStorage.getItem('become-language');
      localStorage.clear();
      if (lang) localStorage.setItem('become-language', lang);
    });

    // Navigate to a protected page
    await page.goto('/projects');

    // Should be redirected to login
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  });
});
