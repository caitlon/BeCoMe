import { test, expect, Page } from '@playwright/test';

const uniqueId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const TEST_PASSWORD = 'TestPass123!@#';

async function registerUser(page: Page, email: string) {
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
  await firstNameField.fill('Onboard');
  await firstNameField.blur();

  const lastNameField = page.getByPlaceholder('Doe');
  await lastNameField.fill('Tester');
  await lastNameField.blur();

  const submitBtn = page.getByRole('button', { name: 'Create Account' });
  await expect(submitBtn).toBeEnabled({ timeout: 10000 });
  await submitBtn.click();

  await expect(page).toHaveURL('/projects', { timeout: 10000 });
}

test.describe('Onboarding Flow', () => {
  test('navigate through all 6 steps and finish', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `onboard-full-${uniqueId()}@test.com`;
    await registerUser(page, email);

    await page.goto('/onboarding');

    // Step 1: Welcome — click "Get Started"
    await expect(page.getByText('Step 1 of 6')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Welcome to BeCoMe')).toBeVisible();
    await page.getByRole('button', { name: /get started/i }).click();

    // Step 2: Create Project
    await expect(page.getByText('Step 2 of 6')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Create a Project')).toBeVisible();
    await page.getByRole('button', { name: /next/i }).click();

    // Step 3: Invite Experts
    await expect(page.getByText('Step 3 of 6')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Invite Experts')).toBeVisible();
    await page.getByRole('button', { name: /next/i }).click();

    // Step 4: Enter Opinion
    await expect(page.getByText('Step 4 of 6')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Enter Your Opinion')).toBeVisible();
    await page.getByRole('button', { name: /next/i }).click();

    // Step 5: View Results
    await expect(page.getByText('Step 5 of 6')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('View Results')).toBeVisible();
    await page.getByRole('button', { name: /next/i }).click();

    // Step 6: Complete — click "Go to Projects"
    await expect(page.getByText('Step 6 of 6')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("You're Ready!")).toBeVisible();
    await page.getByRole('button', { name: /go to projects/i }).click();

    // Redirected to projects page
    await expect(page).toHaveURL('/projects', { timeout: 10000 });

    await page.close();
    await context.close();
  });

  test('previous button navigates back', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `onboard-prev-${uniqueId()}@test.com`;
    await registerUser(page, email);

    await page.goto('/onboarding');

    // Go to step 2
    await expect(page.getByText('Step 1 of 6')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: /get started/i }).click();
    await expect(page.getByText('Step 2 of 6')).toBeVisible({ timeout: 5000 });

    // Go back to step 1
    await page.getByRole('button', { name: /previous/i }).click();
    await expect(page.getByText('Step 1 of 6')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Welcome to BeCoMe')).toBeVisible();

    await page.close();
    await context.close();
  });

  test('skip button exits to projects', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `onboard-skip-${uniqueId()}@test.com`;
    await registerUser(page, email);

    await page.goto('/onboarding');
    await expect(page.getByText('Step 1 of 6')).toBeVisible({ timeout: 10000 });

    // Click "Skip tour"
    await page.getByRole('button', { name: /skip/i }).click();

    // Redirected to projects
    await expect(page).toHaveURL('/projects', { timeout: 10000 });

    await page.close();
    await context.close();
  });

  test('ArrowRight/Left navigate, Escape exits', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `onboard-keys-${uniqueId()}@test.com`;
    await registerUser(page, email);

    await page.goto('/onboarding');
    await expect(page.getByText('Step 1 of 6')).toBeVisible({ timeout: 10000 });

    // ArrowRight → Step 2
    await page.keyboard.press('ArrowRight');
    await expect(page.getByText('Step 2 of 6')).toBeVisible({ timeout: 5000 });

    // ArrowLeft → Step 1
    await page.keyboard.press('ArrowLeft');
    await expect(page.getByText('Step 1 of 6')).toBeVisible({ timeout: 5000 });

    // Escape → /projects
    await page.keyboard.press('Escape');
    await expect(page).toHaveURL('/projects', { timeout: 10000 });

    await page.close();
    await context.close();
  });
});
