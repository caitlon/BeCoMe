import { test as base, expect } from '@playwright/test';

const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript(() => {
      localStorage.setItem('become-language', 'en');
    });
    await use(page);
  },
});

export { test, expect };
