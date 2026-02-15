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

test.describe.serial('Project Actions Flow', () => {
  let ownerContext: BrowserContext;
  let expertContext: BrowserContext;
  let ownerPage: Page;
  let expertPage: Page;
  let projectName: string;
  const ownerEmail = `actions-owner-${uniqueId()}@test.com`;
  const expertEmail = `actions-expert-${uniqueId()}@test.com`;

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

  test('owner and expert register', async () => {
    await registerUser(ownerPage, ownerEmail, 'Action', 'Owner');
    await registerUser(expertPage, expertEmail, 'Action', 'Expert');
  });

  test('owner creates project and invites expert', async () => {
    projectName = `Actions Flow ${Date.now()}`;

    await ownerPage.getByRole('button', { name: 'Create Your First Project' }).click();
    const dialog = ownerPage.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await dialog.getByPlaceholder('Enter project name').fill(projectName);
    await dialog.getByLabel('Unit').fill('%');
    await dialog.getByRole('button', { name: 'Create Project' }).click();
    await expect(dialog).toBeHidden({ timeout: 10000 });

    // Navigate to project
    await ownerPage.getByRole('link', { name: projectName }).click();
    await expect(ownerPage).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Invite expert
    await ownerPage.getByRole('button', { name: 'Invite Experts' }).click();
    const inviteDialog = ownerPage.getByRole('dialog');
    await expect(inviteDialog).toBeVisible();

    await inviteDialog.getByPlaceholder('expert@example.com').fill(expertEmail);
    await inviteDialog.getByRole('button', { name: 'Send Invitation' }).click();
    await expect(inviteDialog.getByText('Invitation sent!')).toBeVisible({ timeout: 10000 });
    await inviteDialog.getByRole('button', { name: 'Done' }).click();
  });

  test('expert accepts invitation and submits opinion', async () => {
    await expertPage.reload();
    await expertPage.waitForLoadState('networkidle');

    // Accept invitation
    await expertPage.getByRole('tab', { name: 'Invitations' }).click();
    await expect(expertPage.getByText(projectName)).toBeVisible({ timeout: 10000 });
    await expertPage.getByRole('button', { name: 'Accept Invitation' }).click();

    // Navigate to project
    await expertPage.getByRole('tab', { name: /Projects/i }).click();
    await expertPage.getByRole('link', { name: projectName }).click();
    await expect(expertPage).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Submit opinion
    await expertPage.getByLabel('Position').first().fill('Expert Tester');
    await expertPage.getByLabel('Lower (pessimistic)').first().fill('30');
    await expertPage.getByLabel('Peak (most likely)').first().fill('50');
    await expertPage.getByLabel('Upper (optimistic)').first().fill('70');

    await expertPage.getByRole('button', { name: 'Save Opinion' }).click();
    await expect(expertPage.getByText('Opinion saved', { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test('expert deletes own opinion', async () => {
    // Reload to ensure fetchData() from previous save has completed
    await expertPage.reload();
    await expertPage.waitForLoadState('networkidle');

    // Delete opinion button should be visible after saving
    const deleteBtn = expertPage.getByRole('button', { name: /delete my opinion/i }).first();
    await expect(deleteBtn).toBeVisible({ timeout: 10000 });
    await deleteBtn.click();

    // Toast confirms deletion
    await expect(expertPage.getByText('Opinion deleted', { exact: true }).first()).toBeVisible({ timeout: 5000 });

    // Form should be empty (Save Opinion button instead of Update)
    await expect(expertPage.getByRole('button', { name: 'Save Opinion' })).toBeVisible({ timeout: 5000 });
  });

  test('expert re-submits opinion for next test', async () => {
    await expertPage.getByLabel('Position').first().fill('Re-Expert');
    await expertPage.getByLabel('Lower (pessimistic)').first().fill('25');
    await expertPage.getByLabel('Peak (most likely)').first().fill('45');
    await expertPage.getByLabel('Upper (optimistic)').first().fill('65');

    await expertPage.getByRole('button', { name: 'Save Opinion' }).click();
    await expect(expertPage.getByText('Opinion saved', { exact: true })).toBeVisible({
      timeout: 5000,
    });
  });

  test('owner removes team member', async () => {
    // Reload to see updated team
    await ownerPage.reload();
    await expect(ownerPage).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Find the remove button for the expert (the X button in team table)
    const removeButton = ownerPage.getByRole('button', { name: /remove.*action expert/i });
    await expect(removeButton).toBeVisible({ timeout: 10000 });
    await removeButton.click();

    // Toast confirms removal
    await expect(ownerPage.getByText('Member removed', { exact: true }).first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe.serial('Decline Invitation Flow', () => {
  let ownerContext: BrowserContext;
  let expertContext: BrowserContext;
  let ownerPage: Page;
  let expertPage: Page;
  let projectName: string;
  const ownerEmail = `decline-owner-${uniqueId()}@test.com`;
  const expertEmail = `decline-expert-${uniqueId()}@test.com`;

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

  test('setup: register users and create project', async () => {
    await registerUser(ownerPage, ownerEmail, 'Decline', 'Owner');
    await registerUser(expertPage, expertEmail, 'Decline', 'Expert');

    projectName = `Decline Flow ${Date.now()}`;
    await ownerPage.getByRole('button', { name: 'Create Your First Project' }).click();
    const dialog = ownerPage.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await dialog.getByPlaceholder('Enter project name').fill(projectName);
    await dialog.getByLabel('Unit').fill('%');
    await dialog.getByRole('button', { name: 'Create Project' }).click();
    await expect(dialog).toBeHidden({ timeout: 10000 });

    // Owner invites expert
    await ownerPage.getByRole('link', { name: projectName }).click();
    await expect(ownerPage).toHaveURL(/\/projects\//, { timeout: 10000 });

    await ownerPage.getByRole('button', { name: 'Invite Experts' }).click();
    const inviteDialog = ownerPage.getByRole('dialog');
    await expect(inviteDialog).toBeVisible();

    await inviteDialog.getByPlaceholder('expert@example.com').fill(expertEmail);
    await inviteDialog.getByRole('button', { name: 'Send Invitation' }).click();
    await expect(inviteDialog.getByText('Invitation sent!')).toBeVisible({ timeout: 10000 });
    await inviteDialog.getByRole('button', { name: 'Done' }).click();
  });

  test('expert declines invitation', async () => {
    // Navigate to projects page explicitly
    await expertPage.goto('/projects');
    await expertPage.waitForLoadState('networkidle');

    // Switch to Invitations tab
    await expertPage.getByRole('tab', { name: 'Invitations' }).click();
    await expect(expertPage.getByText(projectName)).toBeVisible({ timeout: 10000 });

    // Decline the invitation
    await expertPage.getByRole('button', { name: 'Decline' }).first().click();

    // After decline + fetchData(), the Decline button should be gone (no more invitations)
    await expect(expertPage.getByRole('button', { name: 'Decline' })).toBeHidden({ timeout: 10000 });
  });
});
