import { test, expect, Page } from '@playwright/test';

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

async function createProjectAndNavigate(page: Page, name: string) {
  await page.getByRole('button', { name: 'Create Your First Project' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();

  await dialog.getByPlaceholder('Enter project name').fill(name);
  await dialog.getByLabel('Unit').fill('%');
  await dialog.getByRole('button', { name: 'Create Project' }).click();
  await expect(dialog).toBeHidden({ timeout: 10000 });

  await page.getByRole('link', { name: name }).click();
  await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });
}

test.describe('Project Detail — Edge Cases', () => {
  test('empty project shows no results message', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `detail-empty-${uniqueId()}@test.com`;
    await registerAndLogin(page, email, 'Empty', 'Project');

    const projectName = `Empty Project ${Date.now()}`;
    await createProjectAndNavigate(page, projectName);

    // No results message: "Results will appear once experts submit their opinions."
    await expect(page.getByText(/results will appear/i)).toBeVisible({ timeout: 10000 });

    await page.close();
    await context.close();
  });

  test('update existing opinion shows Update button and confirms', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `detail-update-${uniqueId()}@test.com`;
    await registerAndLogin(page, email, 'Updater', 'Tester');

    const projectName = `Update Test ${Date.now()}`;
    await createProjectAndNavigate(page, projectName);

    // Submit initial opinion
    await page.getByLabel('Position').first().fill('Tester');
    await page.getByLabel('Lower (pessimistic)').first().fill('20');
    await page.getByLabel('Peak (most likely)').first().fill('40');
    await page.getByLabel('Upper (optimistic)').first().fill('60');

    await page.getByRole('button', { name: 'Save Opinion' }).click();
    await expect(page.getByText('Opinion saved', { exact: true })).toBeVisible({ timeout: 5000 });

    // Wait for fetchData() to complete — button text changes to "Update Opinion"
    const updateBtn = page.getByRole('button', { name: 'Update Opinion' });
    await expect(updateBtn).toBeVisible({ timeout: 10000 });
    await expect(updateBtn).toBeDisabled();

    // Now change a value to enable the button (fetchData already done, won't overwrite)
    const peakField = page.getByLabel('Peak (most likely)').first();
    await peakField.clear();
    await peakField.fill('50');
    await peakField.blur();

    // Button should now be enabled
    await expect(updateBtn).toBeEnabled({ timeout: 5000 });
    await updateBtn.click();
    await expect(page.getByText('Opinion saved', { exact: true })).toBeVisible({ timeout: 5000 });

    await page.close();
    await context.close();
  });

  test('switch Triangle and Centroid visualization tabs', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `detail-viz-${uniqueId()}@test.com`;
    await registerAndLogin(page, email, 'Viz', 'Tester');

    const projectName = `Viz Tabs ${Date.now()}`;
    await createProjectAndNavigate(page, projectName);

    // Submit opinion so results appear
    await page.getByLabel('Position').first().fill('Viz Expert');
    await page.getByLabel('Lower (pessimistic)').first().fill('20');
    await page.getByLabel('Peak (most likely)').first().fill('40');
    await page.getByLabel('Upper (optimistic)').first().fill('60');

    await page.getByRole('button', { name: 'Save Opinion' }).click();
    await expect(page.getByText('Opinion saved', { exact: true })).toBeVisible({ timeout: 5000 });

    // Results and visualization should be visible
    await expect(page.getByRole('heading', { name: /Best Compromise/ })).toBeVisible({
      timeout: 10000,
    });

    // Default tab is Triangle
    const triangleTab = page.getByRole('tab', { name: /triangle/i });
    const centroidTab = page.getByRole('tab', { name: /centroid/i });

    await expect(triangleTab).toBeVisible();
    await expect(centroidTab).toBeVisible();

    // Switch to Centroid tab
    await centroidTab.click();

    // Switch back to Triangle tab
    await triangleTab.click();

    await page.close();
    await context.close();
  });

  test('toggle Show Individual Opinions checkbox', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `detail-indiv-${uniqueId()}@test.com`;
    await registerAndLogin(page, email, 'Indiv', 'Tester');

    const projectName = `Individual ${Date.now()}`;
    await createProjectAndNavigate(page, projectName);

    // Submit opinion
    await page.getByLabel('Position').first().fill('Individual Expert');
    await page.getByLabel('Lower (pessimistic)').first().fill('30');
    await page.getByLabel('Peak (most likely)').first().fill('50');
    await page.getByLabel('Upper (optimistic)').first().fill('70');

    await page.getByRole('button', { name: 'Save Opinion' }).click();
    await expect(page.getByText('Opinion saved', { exact: true })).toBeVisible({ timeout: 5000 });

    // Wait for results
    await expect(page.getByRole('heading', { name: /Best Compromise/ })).toBeVisible({
      timeout: 10000,
    });

    // Find and toggle the checkbox
    const checkbox = page.getByLabel(/show individual/i);
    await expect(checkbox).toBeVisible();

    // Toggle on
    await checkbox.check();
    await expect(checkbox).toBeChecked();

    // Toggle off
    await checkbox.uncheck();
    await expect(checkbox).not.toBeChecked();

    await page.close();
    await context.close();
  });

  test('language switch to Czech persists across navigation', async ({ browser }) => {
    // Do NOT use addInitScript here — it would override language on every navigation
    const context = await browser.newContext();
    const page = await context.newPage();

    // Set English once before first load
    await page.goto('/');
    await page.evaluate(() => localStorage.setItem('become-language', 'en'));
    await page.reload();
    await expect(page.getByText(/best compromise/i).first()).toBeVisible({ timeout: 10000 });

    // Switch to Czech (aria-label is "Switch to Čeština")
    await page.getByRole('button', { name: /Switch to Čeština/i }).click();

    // Verify Czech text appears on landing page
    await expect(page.getByText(/Nejlepší kompromis/i).first()).toBeVisible({ timeout: 5000 });

    // Navigate to about page — Czech should persist (no initScript overriding)
    await page.goto('/about');

    // "O metodě BeCoMe" is the Czech about page title
    await expect(page.getByText('O metodě BeCoMe')).toBeVisible({ timeout: 10000 });

    await page.close();
    await context.close();
  });
});
