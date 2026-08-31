import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // One worker per core on the CI runner. The whole run is worker-bound: 1049 seconds
  // of test time finished in 528 on two workers, so the wall clock is the total divided
  // by this number and nothing else. Two was a precaution against the visual-regression
  // project comparing screenshots under load, which cost the other 97% of the run more
  // than it protected: those eight tests are 31 seconds of the 1049. CI now runs them
  // as a separate pass at one worker, so the precaution holds and the rest go wide.
  workers: process.env.CI ? 4 : undefined,
  // `list` alongside `html`: the HTML report is written to a directory that CI only
  // uploads when the job fails, so a green run left no record of where its nine
  // minutes went. `list` prints a line and a duration per test into the job log,
  // which is what makes the slow projects visible without re-running anything.
  reporter: [['list'], ['html']],
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
