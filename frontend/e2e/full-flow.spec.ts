import { test, expect, Page } from '@playwright/test';

const TEST_USER = {
  email: `e2e-${Date.now()}@test.com`,
  password: 'TestPass123!@#',
  firstName: 'E2E',
  lastName: 'Tester',
};

test.describe.serial('Full Application Flow', () => {
  let page: Page;
  let projectName: string;

  // Serial tests share a single page instance across all tests,
  // so we create the page manually instead of using the base fixture
  // which creates a new page per test.
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

  test('register a new account and see empty projects', async () => {
    await page.goto('/register');

    await page.getByPlaceholder('you@example.com').fill(TEST_USER.email);
    await page.getByPlaceholder('Min. 12 characters').fill(TEST_USER.password);
    await page.getByPlaceholder('Confirm your password').fill(TEST_USER.password);
    await page.getByPlaceholder('John').fill(TEST_USER.firstName);
    await page.getByPlaceholder('Doe').fill(TEST_USER.lastName);
    await page.getByPlaceholder('Doe').blur();

    const submitBtn = page.getByRole('button', { name: 'Create Account' });
    await expect(submitBtn).toBeEnabled({ timeout: 10000 });
    await submitBtn.click();

    await expect(page).toHaveURL('/projects', { timeout: 10000 });
    await expect(page.getByText('No projects yet')).toBeVisible();
  });

  test('logout and login with created account', async () => {
    // Clear auth state, keep language
    await page.evaluate(() => {
      const lang = localStorage.getItem('become-language');
      localStorage.clear();
      if (lang) localStorage.setItem('become-language', lang);
    });

    await page.goto('/login');

    await page.getByPlaceholder('you@example.com').fill(TEST_USER.email);
    await page.getByPlaceholder('Enter your password').fill(TEST_USER.password);

    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL('/projects', { timeout: 10000 });
  });

  test('create a new project', async () => {
    projectName = `E2E Project ${Date.now()}`;

    await page.getByRole('button', { name: 'Create Your First Project' }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await dialog.getByPlaceholder('Enter project name').fill(projectName);
    await dialog.locator('#scale-unit').fill('%');

    await dialog.getByRole('button', { name: 'Create Project' }).click();

    // Modal closes, project appears in list
    await expect(dialog).toBeHidden({ timeout: 10000 });
    await expect(page.getByText(projectName)).toBeVisible();
  });

  test('submit an opinion on the project', async () => {
    await page.getByRole('link', { name: projectName }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Fill opinion form
    await page.locator('#position').fill('E2E Test Expert');
    await page.locator('#opinion-lower').fill('30');
    await page.locator('#opinion-peak').fill('50');
    await page.locator('#opinion-upper').fill('70');

    await page.getByRole('button', { name: 'Save Opinion' }).click();

    await expect(page.getByText('Opinion saved')).toBeVisible({ timeout: 5000 });
  });

  test('view calculation results', async () => {
    await expect(page.getByText('Best Compromise')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Arithmetic Mean/)).toBeVisible();
    await expect(page.getByText(/Median/)).toBeVisible();
    await expect(page.getByText(/Max Error/)).toBeVisible();

    // Single expert (30, 50, 70): all aggregates equal input
    await expect(page.getByText('30.00').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('50.00').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('70.00').first()).toBeVisible({ timeout: 5000 });
  });
});
