import { test, expect } from '@playwright/test';
import { uniqueId, registerUser } from './helpers';

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
