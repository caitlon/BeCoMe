import { test, expect, Page } from '@playwright/test';

import { TEST_PASSWORD, activateAccount, signIn, submitRegistration } from './helpers';

const uniqueId = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
const TEST_USER = {
  email: `test-${uniqueId}@test.com`,
  password: TEST_PASSWORD,
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

  test('register a new account, activate it, and see empty projects', async () => {
    // Registration only mails a link now, so reaching /projects takes the whole
    // journey: submit, redeem the emailed link with the password it carries, sign in.
    await submitRegistration(page, TEST_USER.email, TEST_USER.firstName, TEST_USER.lastName);
    await activateAccount(page, TEST_USER.email);
    await signIn(page, TEST_USER.email);

    await expect(page.getByText('No projects yet')).toBeVisible();
  });

  test('logout and login with created account', async () => {
    // Clear auth state, keep language. The session lives in HttpOnly cookies now, so
    // clearing localStorage alone is not enough -- clear the cookies to actually log out.
    await page.context().clearCookies();
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
    await dialog.getByLabel('Unit').fill('%');

    await dialog.getByRole('button', { name: 'Create Project' }).click();

    // Modal closes, project appears in list
    await expect(dialog).toBeHidden({ timeout: 10000 });
    await expect(page.getByText(projectName)).toBeVisible();
  });

  test('submit an opinion on the project', async () => {
    await page.getByRole('link', { name: projectName }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Fill opinion form using accessible label selectors
    await page.getByLabel('Position').first().fill('Test Expert');
    await page.getByLabel('Lower (pessimistic)').first().fill('30');
    await page.getByLabel('Peak (most likely)').first().fill('50');
    await page.getByLabel('Upper (optimistic)').first().fill('70');

    await page.getByRole('button', { name: 'Save Opinion' }).click();

    await expect(page.getByText('Opinion saved', { exact: true })).toBeVisible({ timeout: 5000 });
  });

  test('view calculation results', async () => {
    await expect(page.getByRole('heading', { name: /Best Compromise/ })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/How closely the mean and median/)).toBeVisible();
    // Arithmetic Mean and Median live in a collapsed "Supporting calculations" section
    await page.getByRole('button', { name: /Supporting calculations/ }).click();
    await expect(page.getByRole('heading', { name: /Arithmetic Mean/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Median/ })).toBeVisible();

    // Single expert (30, 50, 70): all aggregates equal input
    await expect(page.getByText('30.00').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('50.00').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('70.00').first()).toBeVisible({ timeout: 5000 });
  });
});
