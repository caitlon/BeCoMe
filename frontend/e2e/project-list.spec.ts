import { test, expect, Page } from '@playwright/test';

const uniqueId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const TEST_PASSWORD = 'TestPass123!@#';

async function registerUser(page: Page, email: string) {
  await page.goto('/register');
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('you@example.com').blur();
  await page.getByPlaceholder('Min. 12 characters').fill(TEST_PASSWORD);
  await page.getByPlaceholder('Min. 12 characters').blur();
  await page.getByPlaceholder('Confirm your password').fill(TEST_PASSWORD);
  await page.getByPlaceholder('Confirm your password').blur();
  await page.getByPlaceholder('John').fill('List');
  await page.getByPlaceholder('John').blur();
  await page.getByPlaceholder('Doe').fill('Tester');
  await page.getByPlaceholder('Doe').blur();

  const submitBtn = page.getByRole('button', { name: 'Create Account' });
  await expect(submitBtn).toBeEnabled({ timeout: 10000 });
  await submitBtn.click();
  await expect(page).toHaveURL('/projects', { timeout: 10000 });
}

test.describe('Project List', () => {
  test('multiple projects display in grid', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `list-multi-${uniqueId()}@test.com`;
    await registerUser(page, email);

    const projectNames: string[] = [];

    // Create 5 projects
    for (let i = 1; i <= 5; i++) {
      const name = `Grid Project ${i} ${Date.now()}`;
      projectNames.push(name);

      const createBtn =
        i === 1
          ? page.getByRole('button', { name: 'Create Your First Project' })
          : page.getByRole('button', { name: 'New Project' });

      await createBtn.click();
      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();

      await dialog.getByPlaceholder('Enter project name').fill(name);
      await dialog.getByLabel('Unit').fill('%');
      await dialog.getByRole('button', { name: 'Create Project' }).click();
      await expect(dialog).toBeHidden({ timeout: 10000 });
    }

    // All 5 projects should be visible on /projects
    for (const name of projectNames) {
      await expect(page.getByRole('link', { name })).toBeVisible({ timeout: 10000 });
    }

    await page.close();
    await context.close();
  });
});
