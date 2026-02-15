import { test, expect } from './fixtures/base';

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

    // Focus email, then tab through — email comes before password in DOM
    await emailField.focus();
    await expect(emailField).toBeFocused();

    // Tab forward until we reach password (may skip intermediate elements)
    for (let i = 0; i < 5; i++) {
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
    for (let f = 1; f < fields.length; f++) {
      // Tab forward until we reach the next expected field
      for (let i = 0; i < 10; i++) {
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

    const uid = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const email = `a11y-dialog-${uid}@test.com`;

    await page.goto('/register');

    const emailField = page.getByPlaceholder('you@example.com');
    await emailField.fill(email);
    await emailField.blur();

    const passwordField = page.getByPlaceholder('Min. 12 characters');
    await passwordField.fill('TestPass123!@#');
    await passwordField.blur();

    const confirmField = page.getByPlaceholder('Confirm your password');
    await confirmField.fill('TestPass123!@#');
    await confirmField.blur();

    const firstNameField = page.getByPlaceholder('John');
    await firstNameField.fill('Dialog');
    await firstNameField.blur();

    const lastNameField = page.getByPlaceholder('Doe');
    await lastNameField.fill('Tester');
    await lastNameField.blur();

    const submitBtn = page.getByRole('button', { name: 'Create Account' });
    await expect(submitBtn).toBeEnabled({ timeout: 15000 });
    await submitBtn.click();
    await expect(page).toHaveURL('/projects', { timeout: 10000 });

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

    // 11 chars — too short
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

    // 12 chars — meets requirement
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
