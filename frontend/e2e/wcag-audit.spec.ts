import AxeBuilder from '@axe-core/playwright';
import { Page } from '@playwright/test';

import { test, expect } from './fixtures/base';
import { registerUser, uniqueId } from './helpers';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function auditPage(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  return results.violations;
}

test.describe('WCAG Audit — Public Pages', () => {
  test('landing page has no WCAG violations', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('about page has no WCAG violations', async ({ page }) => {
    await page.goto('/about');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('docs page has no WCAG violations', async ({ page }) => {
    await page.goto('/docs');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('FAQ page has no WCAG violations', async ({ page }) => {
    await page.goto('/faq');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('case studies page has no WCAG violations', async ({ page }) => {
    await page.goto('/case-studies');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('case study detail page has no WCAG violations', async ({ page }) => {
    await page.goto('/case-study/budget');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('login page has no WCAG violations', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('register page has no WCAG violations', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });

  test('404 page has no WCAG violations', async ({ page }) => {
    await page.goto('/nonexistent-route');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);
  });
});

test.describe('WCAG Audit — Dark Theme', () => {
  test('landing page in dark theme has no WCAG violations', async ({
    browser,
  }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'en');
      localStorage.setItem('vite-ui-theme', 'dark');
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);

    await page.close();
    await context.close();
  });

  test('login page in dark theme has no WCAG violations', async ({
    browser,
  }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'en');
      localStorage.setItem('vite-ui-theme', 'dark');
    });

    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);

    await page.close();
    await context.close();
  });
});

test.describe('WCAG Audit — Authenticated Pages', () => {
  test('projects page has no WCAG violations', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() =>
      localStorage.setItem('become-language', 'en'),
    );

    const email = `wcag-projects-${uniqueId()}@test.com`;
    await registerUser(page, email, 'WCAG', 'Tester');

    await page.goto('/projects');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);

    await page.close();
    await context.close();
  });

  test('onboarding page has no WCAG violations', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() =>
      localStorage.setItem('become-language', 'en'),
    );

    const email = `wcag-onboarding-${uniqueId()}@test.com`;
    await registerUser(page, email, 'WCAG', 'Tester');

    await page.goto('/onboarding');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);

    await page.close();
    await context.close();
  });

  test('profile page has no WCAG violations', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() =>
      localStorage.setItem('become-language', 'en'),
    );

    const email = `wcag-profile-${uniqueId()}@test.com`;
    await registerUser(page, email, 'WCAG', 'Tester');

    await page.goto('/profile');
    await page.waitForLoadState('networkidle');

    const violations = await auditPage(page);

    expect(violations).toEqual([]);

    await page.close();
    await context.close();
  });
});
