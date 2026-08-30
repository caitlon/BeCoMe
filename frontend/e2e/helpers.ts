import { expect, Page } from '@playwright/test';
import { createHmac } from 'node:crypto';
import { readFile } from 'node:fs/promises';

export const uniqueId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

export const TEST_PASSWORD = 'TestPass123!@#';

// Registration does not open a session any more: the account is created unverified
// and the only way into it is the link the API mails. The E2E runs use the console
// email sender, which prints that link to the API's stdout, and the runner captures
// that stream here. See scripts/ci/e2e-local.sh and the CI job that starts uvicorn.
const API_LOG_PATH = process.env.E2E_API_LOG ?? '/tmp/become-e2e-api.log';

// Each printed line names its recipient by hash_email(address): an HMAC-SHA-256 keyed
// with LOG_HASH_KEY, or SECRET_KEY when that is unset, truncated to 16 hex characters
// (api/auth/logging.py). Recomputing the tag here is what makes the lookup exact.
// Taking the newest link in the file instead would, with several workers registering
// at the same time, sometimes redeem another test's single-use token, passing in
// this test and failing in that one, with nothing in either report to explain it.
const EMAIL_TAG_LENGTH = 16;

const LINK_TIMEOUT_MS = 20_000;
const LINK_POLL_MS = 200;

function logHashKey(): string {
  const key = process.env.LOG_HASH_KEY || process.env.SECRET_KEY;
  if (!key) {
    throw new Error(
      'Set LOG_HASH_KEY or SECRET_KEY for the E2E run, matching the value the API ' +
        'was started with: activation links are found by the keyed tag it prints ' +
        'beside them.'
    );
  }
  return key;
}

function emailTag(email: string): string {
  return createHmac('sha256', logHashKey())
    .update(email.trim().toLowerCase())
    .digest('hex')
    .slice(0, EMAIL_TAG_LENGTH);
}

/**
 * Read the activation link the API printed for an address out of its captured stdout.
 *
 * Polls, because registration answers 202 before the send has necessarily reached the
 * sender, and accepts only a newline-terminated line so a half-written one is never
 * parsed as a truncated token.
 */
export async function activationLinkFor(email: string): Promise<string> {
  const marker = `verification link for ${emailTag(email)}: `;
  const deadline = Date.now() + LINK_TIMEOUT_MS;
  let readFailure = '';

  while (Date.now() < deadline) {
    let log = '';
    try {
      log = await readFile(API_LOG_PATH, 'utf8');
    } catch (error) {
      readFailure = `${error}`;
    }
    const at = log.lastIndexOf(marker);
    if (at !== -1) {
      const rest = log.slice(at + marker.length);
      const newline = rest.indexOf('\n');
      if (newline !== -1) {
        const link = rest.slice(0, newline).trim();
        if (link) return link;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, LINK_POLL_MS));
  }

  throw new Error(
    `No activation link for ${email} reached ${API_LOG_PATH} within ${LINK_TIMEOUT_MS} ms.` +
      (readFailure ? ` Last read error: ${readFailure}.` : '') +
      ' Check that the API runs with its stdout redirected there and PYTHONUNBUFFERED=1,' +
      ' that EMAIL_PROVIDER is console, and that both processes share one SECRET_KEY.'
  );
}

/**
 * Fill in and submit the registration form, stopping at the check-your-inbox state.
 *
 * That state is where the flow now ends for the browser: there is no session and no
 * redirect, only an acknowledgement that something was mailed.
 */
export async function submitRegistration(
  page: Page,
  email: string,
  firstName = 'Test',
  lastName = 'User',
) {
  await page.goto('/register');

  const emailField = page.getByPlaceholder('you@example.com');
  await emailField.fill(email);
  await emailField.blur();

  const passwordField = page.getByPlaceholder('Min. 12 characters');
  await passwordField.fill(TEST_PASSWORD);
  await passwordField.blur();

  const confirmField = page.getByPlaceholder('Confirm your password');
  await confirmField.fill(TEST_PASSWORD);
  await confirmField.blur();

  const firstNameField = page.getByPlaceholder('John');
  await firstNameField.fill(firstName);
  await firstNameField.blur();

  const lastNameField = page.getByPlaceholder('Doe');
  await lastNameField.fill(lastName);
  await lastNameField.blur();

  const submitBtn = page.getByRole('button', { name: 'Create Account' });
  await expect(submitBtn).toBeEnabled({ timeout: 10000 });
  await submitBtn.click();

  await expect(
    page.getByRole('heading', { name: 'Check your inbox', level: 1 })
  ).toBeVisible({ timeout: 10000 });
}

/**
 * Open the emailed activation link and confirm the account with its password.
 *
 * The link is built from the API's FRONTEND_BASE_URL; navigating by path keeps this
 * working against the Playwright origin whether or not that setting points at it.
 */
export async function activateAccount(page: Page, email: string, password = TEST_PASSWORD) {
  const link = new URL(await activationLinkFor(email));
  await page.goto(`${link.pathname}${link.search}`);

  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByRole('button', { name: 'Confirm email' }).click();

  await expect(page).toHaveURL('/login', { timeout: 10000 });
}

/** Sign in through the login form and land on the projects page. */
export async function signIn(page: Page, email: string, password = TEST_PASSWORD) {
  await page.goto('/login');
  await page.getByPlaceholder('you@example.com').fill(email);
  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();

  await expect(page).toHaveURL('/projects', { timeout: 15000 });
}

/**
 * Take an address all the way from the registration form to a signed-in session.
 *
 * Every step is the one a real user takes, including redeeming the mailed link: an
 * account that skipped it could not log in at all, so there is no shortcut to take.
 */
export async function registerUser(
  page: Page,
  email: string,
  firstName = 'Test',
  lastName = 'User',
) {
  await submitRegistration(page, email, firstName, lastName);
  await activateAccount(page, email);
  await signIn(page, email);
}
