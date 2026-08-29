import { test, expect } from './fixtures/base';
import { uniqueId, registerUser } from './helpers';

async function countTabbableElements(page: import('@playwright/test').Page): Promise<number> {
  return page.evaluate(() =>
    document.querySelectorAll(
      'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
    ).length,
  );
}

test.describe('Accessibility - Skip Link', () => {
  test('the skip link is first in tab order and reveals itself on focus', async ({ page }) => {
    await page.goto('/');

    const skip = page.locator('a.skip-to-content');

    // It has to be the first thing a keyboard reaches, or it cannot bypass the navbar.
    // Asserted structurally rather than by pressing Tab: Firefox does not move focus
    // into a freshly loaded document on the first press, so that would test the engine.
    const firstTabbable = await page.evaluate(
      () =>
        document.querySelector(
          'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])',
        )?.className,
    );
    expect(firstTabbable).toBe('skip-to-content');

    // Present but out of the layout until it takes focus, then pinned on screen.
    expect(await skip.evaluate((el) => el.getBoundingClientRect().left)).toBeLessThan(0);
    await skip.focus();
    await expect(skip).toBeFocused();
    expect(await skip.evaluate((el) => el.getBoundingClientRect().left)).toBeGreaterThanOrEqual(0);

    // Activating it hands focus to the landmark, which is the whole point of the control.
    await page.keyboard.press('Enter');
    await expect(page.locator('#main-content')).toBeFocused();
  });
});

test.describe('Accessibility — Tab Order', () => {
  test('login form fields are keyboard-focusable in order', async ({ page }) => {
    await page.goto('/login');

    // All form fields should be focusable via click + Tab navigation
    const emailField = page.getByPlaceholder('you@example.com');
    const passwordField = page.getByPlaceholder('Enter your password');
    const submitBtn = page.getByRole('button', { name: 'Sign In' });

    // Verify all fields exist and are visible
    await expect(emailField).toBeVisible();
    await expect(passwordField).toBeVisible();
    await expect(submitBtn).toBeVisible();

    // Focus email, then tab through: email comes before password in DOM
    await emailField.focus();
    await expect(emailField).toBeFocused();

    // Tab forward until we reach password (dynamic cap based on tabbable elements)
    const maxTabs = await countTabbableElements(page);
    for (let i = 0; i < maxTabs; i++) {
      await page.keyboard.press('Tab');
      if (await passwordField.evaluate((el) => el === document.activeElement)) break;
    }
    await expect(passwordField).toBeFocused();
  });

  test('register form fields are keyboard-focusable in order', async ({ page }) => {
    await page.goto('/register');

    const fields = [
      page.getByPlaceholder('you@example.com'),
      page.getByPlaceholder('Min. 12 characters'),
      page.getByPlaceholder('Confirm your password'),
      page.getByPlaceholder('John'),
      page.getByPlaceholder('Doe'),
    ];

    // All fields should be visible
    for (const field of fields) {
      await expect(field).toBeVisible();
    }

    // Focus first field
    await fields[0].focus();
    await expect(fields[0]).toBeFocused();

    // Tab through and verify each subsequent field receives focus
    const maxTabs = await countTabbableElements(page);
    for (let f = 1; f < fields.length; f++) {
      // Tab forward until we reach the next expected field
      for (let i = 0; i < maxTabs; i++) {
        await page.keyboard.press('Tab');
        if (await fields[f].evaluate((el) => el === document.activeElement)) break;
      }
      await expect(fields[f]).toBeFocused();
    }
  });
});

test.describe('Accessibility — Dialog Focus', () => {
  test('dialog opens and closes with Escape', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const email = `a11y-dialog-${uniqueId()}@test.com`;
    await registerUser(page, email, 'Dialog', 'Tester');

    // Open create project dialog
    const createBtn = page.getByRole('button', { name: 'Create Your First Project' });
    await expect(createBtn).toBeVisible({ timeout: 10000 });
    await createBtn.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Escape closes dialog
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden({ timeout: 5000 });

    await page.close();
    await context.close();
  });
});

test.describe('Accessibility — Password Validation Boundary', () => {
  test('password 12-char boundary', async ({ page }) => {
    await page.goto('/register');

    const passwordField = page.getByPlaceholder('Min. 12 characters');

    // 11 chars, too short
    await passwordField.fill('Abcdefgh12!');
    await passwordField.blur();

    // Submit button should be disabled (password too short)
    const submitButton = page.getByRole('button', { name: 'Create Account' });

    // Fill all other fields so only password length blocks submission
    await page.getByPlaceholder('you@example.com').fill(`boundary-${Date.now()}@test.com`);
    await page.getByPlaceholder('you@example.com').blur();
    await page.getByPlaceholder('Confirm your password').fill('Abcdefgh12!');
    await page.getByPlaceholder('Confirm your password').blur();
    await page.getByPlaceholder('John').fill('Boundary');
    await page.getByPlaceholder('John').blur();
    await page.getByPlaceholder('Doe').fill('Test');
    await page.getByPlaceholder('Doe').blur();

    // With 11-char password, submit should be disabled
    await expect(submitButton).toBeDisabled({ timeout: 5000 });

    // 12 chars, meets requirement
    await passwordField.clear();
    await passwordField.fill('Abcdefgh123!');
    await passwordField.blur();
    await page.getByPlaceholder('Confirm your password').clear();
    await page.getByPlaceholder('Confirm your password').fill('Abcdefgh123!');
    await page.getByPlaceholder('Confirm your password').blur();

    // Submit button should now be enabled
    await expect(submitButton).toBeEnabled({ timeout: 10000 });
  });
});
