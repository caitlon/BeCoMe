import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // Two, and four was measured and rejected. The runner advertises four cores but has
  // two physical ones behind them, and a browser per worker does not fit in a
  // hyperthread sibling: at four workers the summed test time went from 1049 seconds
  // to 1787, so 70% more work bought 13% less wall clock. Six webkit tests also began
  // failing on the timeout, which is what that inflation looks like from the inside.
  // More parallelism here needs more machines, not more workers on this one.
  workers: process.env.CI ? 2 : undefined,
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
      testIgnore: /visual-regression|wcag-audit|docs-screenshots/,
    },
    // Firefox and WebKit get twice the default timeout, because they are that much
    // slower on the same specs: summed over one CI run, chromium spends 225 seconds
    // where firefox spends 304 and webkit 442. At two workers webkit's slowest test
    // finished in 26.7s against the 30s default, so the margin was three seconds and
    // it was the worker count holding it, not the app. Going to four workers pushed
    // webkit to 32.7s and firefox to 30.7s, and six tests failed on the timeout alone.
    // The number belongs to the browser rather than to how the run was scheduled.
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      testIgnore: /visual-regression|wcag-audit|docs-screenshots/,
      timeout: 60_000,
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      testIgnore: /visual-regression|wcag-audit|docs-screenshots/,
      timeout: 60_000,
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
    // Illustrations for the documentation site, not a check. It writes PNGs into
    // `docs/user/img/` and asserts almost nothing, so it is opt-in: nothing runs it
    // unless somebody names it, and the three browser projects above ignore it.
    {
      name: 'docs-screenshots',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /docs-screenshots/,
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
