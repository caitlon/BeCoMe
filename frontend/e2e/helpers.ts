import { expect, Page } from '@playwright/test';

export const uniqueId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

export const TEST_PASSWORD = 'TestPass123!@#';

export async function registerUser(
  page: Page,
  email: string,
  firstName = 'Test',
  lastName = 'User',
) {
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
