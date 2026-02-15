import { test, expect, Page } from '@playwright/test';
import { uniqueId, registerUser } from './helpers';

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
    await registerUser(page, email, 'Empty', 'Project');

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
    await registerUser(page, email, 'Updater', 'Tester');

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
    await registerUser(page, email, 'Viz', 'Tester');

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
    await registerUser(page, email, 'Indiv', 'Tester');

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

  test('clicking team member opens profile dialog', async ({ browser }) => {
    const ownerContext = await browser.newContext();
    const expertContext = await browser.newContext();
    const ownerPage = await ownerContext.newPage();
    const expertPage = await expertContext.newPage();
    await ownerPage.addInitScript(() => localStorage.setItem('become-language', 'en'));
    await expertPage.addInitScript(() => localStorage.setItem('become-language', 'en'));

    const ownerEmail = `detail-team-owner-${uniqueId()}@test.com`;
    const expertEmail = `detail-team-expert-${uniqueId()}@test.com`;

    await registerUser(ownerPage, ownerEmail, 'Team', 'Owner');
    await registerUser(expertPage, expertEmail, 'Team', 'Expert');

    const projectName = `Team Dialog ${Date.now()}`;
    await createProjectAndNavigate(ownerPage, projectName);

    // Invite expert
    await ownerPage.getByRole('button', { name: 'Invite Experts' }).click();
    const inviteDialog = ownerPage.getByRole('dialog');
    await expect(inviteDialog).toBeVisible();
    await inviteDialog.getByPlaceholder('expert@example.com').fill(expertEmail);
    await inviteDialog.getByRole('button', { name: 'Send Invitation' }).click();
    await expect(inviteDialog.getByText('Invitation sent!')).toBeVisible({ timeout: 10000 });
    await inviteDialog.getByRole('button', { name: 'Done' }).click();

    // Expert accepts
    await expertPage.reload();
    await expertPage.waitForLoadState('networkidle');
    await expertPage.getByRole('tab', { name: 'Invitations' }).click();
    await expect(expertPage.getByText(projectName)).toBeVisible({ timeout: 10000 });
    await expertPage.getByRole('button', { name: 'Accept Invitation' }).click();

    // Owner reloads to see team member
    await ownerPage.reload();
    await ownerPage.waitForLoadState('networkidle');

    // Click team member row to open profile dialog
    const memberRow = ownerPage.getByRole('button', { name: /View profile of Team Expert/i });
    await expect(memberRow).toBeVisible({ timeout: 10000 });
    await memberRow.click();

    // Profile dialog should show member name
    const profileDialog = ownerPage.getByRole('dialog');
    await expect(profileDialog).toBeVisible({ timeout: 5000 });
    await expect(profileDialog.getByText('Team Expert')).toBeVisible();

    // Escape closes dialog
    await ownerPage.keyboard.press('Escape');
    await expect(profileDialog).toBeHidden({ timeout: 5000 });

    await ownerPage.close();
    await expertPage.close();
    await ownerContext.close();
    await expertContext.close();
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
