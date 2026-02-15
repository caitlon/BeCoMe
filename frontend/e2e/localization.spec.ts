import { test, expect } from '@playwright/test';

test.describe('Czech Localization', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'cs');
    });
  });

  test('landing page displays Czech content', async ({ page }) => {
    await page.goto('/');

    // Hero section
    await expect(page.getByText('Skupinová rozhodnutí,')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Přesně změřená')).toBeVisible();

    // How it works section
    await expect(page.getByText('Jak to funguje')).toBeVisible();
    await expect(page.getByText('Sběr')).toBeVisible();
    await expect(page.getByText('Výpočet')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Konsenzus', exact: true })).toBeVisible();

    // Navigation
    await expect(
      page.getByRole('navigation', { name: 'Hlavní navigace' }).getByRole('link', { name: 'O metodě' }),
    ).toBeVisible();
  });

  test('login form shows Czech labels', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByRole('heading', { name: 'Vítejte zpět' })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByPlaceholder('vas@email.cz')).toBeVisible();
    await expect(page.getByPlaceholder('Zadejte heslo')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Přihlásit se' })).toBeVisible();
    await expect(page.getByText('Nemáte účet?')).toBeVisible();
  });

  test('registration form shows Czech labels', async ({ page }) => {
    await page.goto('/register');

    await expect(page.getByRole('heading', { name: 'Vytvořit účet' })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByPlaceholder('Jan')).toBeVisible();
    await expect(page.getByPlaceholder('Novák')).toBeVisible();
    await expect(page.getByPlaceholder('vas@email.cz')).toBeVisible();
    await expect(page.getByPlaceholder('Min. 12 znaků')).toBeVisible();
    await expect(page.getByPlaceholder('Potvrďte heslo')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Vytvořit účet' })).toBeVisible();
  });
});
