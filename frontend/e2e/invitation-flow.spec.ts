import { test, expect, BrowserContext, Page } from '@playwright/test';

const uniqueId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const TEST_PASSWORD = 'TestPass123!@#';

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

test.describe.serial('Invitation Flow', () => {
  let ownerContext: BrowserContext;
  let expertContext: BrowserContext;
  let ownerPage: Page;
  let expertPage: Page;
  let projectName: string;
  const ownerEmail = `owner-${uniqueId()}@test.com`;
  const expertEmail = `expert-${uniqueId()}@test.com`;

  test.beforeAll(async ({ browser }) => {
    ownerContext = await browser.newContext();
    expertContext = await browser.newContext();
    ownerPage = await ownerContext.newPage();
    expertPage = await expertContext.newPage();

    await ownerPage.addInitScript(() => localStorage.setItem('become-language', 'en'));
    await expertPage.addInitScript(() => localStorage.setItem('become-language', 'en'));
  });

  test.afterAll(async () => {
    await ownerPage.close();
    await expertPage.close();
    await ownerContext.close();
    await expertContext.close();
  });

  test('owner registers account', async () => {
    await registerUser(ownerPage, ownerEmail, 'Owner', 'Tester');
  });

  test('expert registers account', async () => {
    await registerUser(expertPage, expertEmail, 'Expert', 'Tester');
  });

  test('owner creates a project', async () => {
    projectName = `Invite Flow ${Date.now()}`;

    await ownerPage.getByRole('button', { name: 'Create Your First Project' }).click();

    const dialog = ownerPage.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await dialog.getByPlaceholder('Enter project name').fill(projectName);
    await dialog.getByLabel('Unit').fill('%');
    await dialog.getByRole('button', { name: 'Create Project' }).click();

    await expect(dialog).toBeHidden({ timeout: 10000 });
    await expect(ownerPage.getByText(projectName)).toBeVisible();
  });

  test('owner navigates to project and invites expert', async () => {
    await ownerPage.getByRole('link', { name: projectName }).click();
    await expect(ownerPage).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Open invite modal
    await ownerPage.getByRole('button', { name: 'Invite Experts' }).click();
    const dialog = ownerPage.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Enter expert email and send invitation
    await dialog.getByPlaceholder('expert@example.com').fill(expertEmail);
    await dialog.getByRole('button', { name: 'Send Invitation' }).click();

    // Wait for success state
    await expect(dialog.getByText('Invitation sent!')).toBeVisible({ timeout: 10000 });
    await dialog.getByRole('button', { name: 'Done' }).click();
  });

  test('expert sees invitation and accepts', async () => {
    // Reload to fetch fresh data (invitation was sent after page loaded)
    await expertPage.reload();
    await expertPage.waitForLoadState('networkidle');

    // Switch to Invitations tab
    await expertPage.getByRole('tab', { name: 'Invitations' }).click();

    // Expert sees the invitation with project name
    await expect(expertPage.getByText(projectName)).toBeVisible({ timeout: 10000 });

    // Accept the invitation
    await expertPage.getByRole('button', { name: 'Accept Invitation' }).click();

    // After accepting, expert should see the project in their list
    await expertPage.getByRole('tab', { name: /Projects/i }).click();
    await expect(expertPage.getByText(projectName)).toBeVisible({ timeout: 10000 });
  });

  test('expert submits an opinion', async () => {
    await expertPage.getByRole('link', { name: projectName }).click();
    await expect(expertPage).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Fill opinion form
    await expertPage.getByLabel('Position').first().fill('Invited Expert');
    await expertPage.getByLabel('Lower (pessimistic)').first().fill('30');
    await expertPage.getByLabel('Peak (most likely)').first().fill('50');
    await expertPage.getByLabel('Upper (optimistic)').first().fill('70');

    await expertPage.getByRole('button', { name: 'Save Opinion' }).click();
    await expect(expertPage.getByText('Opinion saved', { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test('owner submits own opinion', async () => {
    // Owner fills their opinion on the same project
    await ownerPage.getByLabel('Position').first().fill('Project Owner');
    await ownerPage.getByLabel('Lower (pessimistic)').first().fill('20');
    await ownerPage.getByLabel('Peak (most likely)').first().fill('40');
    await ownerPage.getByLabel('Upper (optimistic)').first().fill('60');

    await ownerPage.getByRole('button', { name: 'Save Opinion' }).click();
    await expect(ownerPage.getByText('Opinion saved', { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test('owner sees aggregated results from 2 experts', async () => {
    // Reload to get fresh results
    await ownerPage.reload();
    await expect(ownerPage).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Results section should show calculation from 2 experts
    await expect(
      ownerPage.getByRole('heading', { name: /Best Compromise/ }),
    ).toBeVisible({ timeout: 10000 });
    await expect(ownerPage.getByRole('heading', { name: /Arithmetic Mean/ })).toBeVisible();
    await expect(ownerPage.getByRole('heading', { name: /Median/ })).toBeVisible();

    // Arithmetic mean of (20,40,60) and (30,50,70) = (25,45,65)
    await expect(ownerPage.getByText('25.00').first()).toBeVisible({ timeout: 5000 });
    await expect(ownerPage.getByText('45.00').first()).toBeVisible({ timeout: 5000 });
    await expect(ownerPage.getByText('65.00').first()).toBeVisible({ timeout: 5000 });
  });
});
