import { test, expect, Page } from '@playwright/test';

const uniqueId = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
const TEST_USER = {
  email: `test-${uniqueId}@test.com`,
  password: 'TestPass123!@#',
  firstName: 'Test',
  lastName: 'User',
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

    // Each field needs focus+blur to trigger "onTouched" validation in react-hook-form
    const emailField = page.getByPlaceholder('you@example.com');
    await emailField.fill(TEST_USER.email);
    await emailField.blur();

    const passwordField = page.getByPlaceholder('Min. 12 characters');
    await passwordField.fill(TEST_USER.password);
    await passwordField.blur();

    const confirmField = page.getByPlaceholder('Confirm your password');
    await confirmField.fill(TEST_USER.password);
    await confirmField.blur();

    const firstNameField = page.getByPlaceholder('John');
    await firstNameField.fill(TEST_USER.firstName);
    await firstNameField.blur();

    const lastNameField = page.getByPlaceholder('Doe');
    await lastNameField.fill(TEST_USER.lastName);
    await lastNameField.blur();

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
    await expect(page.getByRole('heading', { name: 'Welcome Back' })).toBeVisible();

    await page.getByPlaceholder('you@example.com').fill(TEST_USER.email);
    await page.getByPlaceholder('Enter your password').fill(TEST_USER.password);

    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL('/projects', { timeout: 15000 });
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

    // Fill opinion form (use .first() — page may render multiple opinion sections)
    await page.locator('#position').first().fill('Test Expert');
    await page.locator('#opinion-lower').first().fill('30');
    await page.locator('#opinion-peak').first().fill('50');
    await page.locator('#opinion-upper').first().fill('70');

    await page.getByRole('button', { name: 'Save Opinion' }).click();

    await expect(page.getByText('Opinion saved', { exact: true })).toBeVisible({ timeout: 5000 });
  });

  test('view calculation results', async () => {
    await expect(page.getByRole('heading', { name: /Best Compromise/ })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: /Arithmetic Mean/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Median/ })).toBeVisible();
    await expect(page.getByText(/Max Error/)).toBeVisible();

    // Single expert (30, 50, 70): all aggregates equal input
    await expect(page.getByText('30.00').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('50.00').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('70.00').first()).toBeVisible({ timeout: 5000 });
  });
});
