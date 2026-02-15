import { test, expect } from '@playwright/test';
import { uniqueId, registerUser } from './helpers';

test.describe('Mobile Responsive', () => {
  test('mobile shows tab layout on project detail', async ({ browser }) => {
    // Start with normal viewport for registration, then resize
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `mobile-tabs-${uniqueId()}@test.com`;
    await registerUser(page, email);

    // Create project at normal viewport
    const createBtn = page.getByRole('button', { name: /Create.*Project/i }).first();
    await expect(createBtn).toBeVisible({ timeout: 10000 });
    await createBtn.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    const projectName = `Mobile Tabs ${Date.now()}`;
    await dialog.getByPlaceholder('Enter project name').fill(projectName);
    await dialog.getByLabel('Unit').fill('%');
    await dialog.getByRole('button', { name: 'Create Project' }).click();
    await expect(dialog).toBeHidden({ timeout: 10000 });

    // Navigate to project
    await page.getByRole('link', { name: projectName }).click();
    await expect(page).toHaveURL(/\/projects\//, { timeout: 10000 });

    // Now resize to mobile viewport
    await page.setViewportSize({ width: 375, height: 812 });

    // Mobile: tabs should be visible (lg:hidden shows Tabs component)
    const opinionsTab = page.getByRole('tab', { name: /opinions/i });
    const resultsTab = page.getByRole('tab', { name: /results/i });
    const teamTab = page.getByRole('tab', { name: /team/i });

    await expect(opinionsTab).toBeVisible({ timeout: 10000 });
    await expect(resultsTab).toBeVisible();
    await expect(teamTab).toBeVisible();

    // Switch between tabs — verify each tab is selectable
    await resultsTab.click();
    await expect(resultsTab).toHaveAttribute('data-state', 'active', { timeout: 5000 });

    await teamTab.click();
    await expect(teamTab).toHaveAttribute('data-state', 'active', { timeout: 5000 });

    await opinionsTab.click();
    await expect(opinionsTab).toHaveAttribute('data-state', 'active', { timeout: 5000 });

    await page.close();
    await context.close();
  });

  test('mobile hamburger menu opens and closes', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 375, height: 812 },
    });
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    await page.goto('/');

    // Hamburger button should be visible on mobile
    const menuButton = page.getByRole('button', { name: 'Open menu' });
    await expect(menuButton).toBeVisible({ timeout: 10000 });
    expect(await menuButton.getAttribute('aria-expanded')).toBe('false');

    // Open menu
    await menuButton.click();

    // Menu should be expanded
    const closeButton = page.getByRole('button', { name: 'Close menu' });
    await expect(closeButton).toBeVisible({ timeout: 5000 });
    expect(await closeButton.getAttribute('aria-expanded')).toBe('true');

    // Escape closes menu
    await page.keyboard.press('Escape');
    await expect(page.getByRole('button', { name: 'Open menu' })).toBeVisible({ timeout: 5000 });

    await page.close();
    await context.close();
  });
});
