import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // The CI runner has 4 cores and fullyParallel is on, so a single worker left three
  // idle and made this the longest job in the pipeline by far. Two is deliberate rather
  // than maximal: the visual-regression project compares screenshots, and rendering
  // under heavy load is where those start to flake.
  workers: process.env.CI ? 2 : undefined,
  reporter: 'html',
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    },
  },
  use: {
    // HTTPS, because the session cookies carry the __Host- prefix and browsers only
    // honour it on a Secure cookie. WebKit will not even store one over plain
    // http://localhost. The certificate is self-signed and regenerated on demand
    // (scripts/e2e-cert.mjs), so the error it raises is expected and ignored here.
    baseURL: 'https://localhost:8080',
    ignoreHTTPSErrors: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: /visual-regression|wcag-audit/,
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      testIgnore: /visual-regression|wcag-audit/,
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      testIgnore: /visual-regression|wcag-audit/,
    },
    {
      name: 'wcag-audit',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /wcag-audit/,
    },
    {
      name: 'visual-regression',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /visual-regression/,
    },
  ],
  webServer: {
    // dev:e2e mints the certificate first; plain `dev` would come up on HTTP and every
    // authenticated test would fail on a cookie the browser refused to store.
    command: 'npm run dev:e2e',
    url: 'https://localhost:8080',
    ignoreHTTPSErrors: true,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
