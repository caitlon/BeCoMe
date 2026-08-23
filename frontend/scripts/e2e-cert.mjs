/**
 * Generate the self-signed certificate the e2e dev server runs on.
 *
 * The suite needs HTTPS because the session cookies carry the `__Host-` prefix, which
 * browsers only honour on a cookie marked `Secure` -- and WebKit refuses to store such a
 * cookie over plain `http://localhost` at all (Chromium and Firefox accept it there, so
 * the gap only shows up in one of the three browsers the suite runs).
 *
 * Written by hand with openssl rather than pulling in a plugin: it is one command, it
 * keeps the dependency tree (and its audit surface) unchanged, and the certificate is
 * throwaway -- regenerated whenever it is missing, never committed, trusted by nobody
 * except Playwright's `ignoreHTTPSErrors`.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";

const CERT_DIR = path.resolve(import.meta.dirname, "..", ".certs");
export const KEY_PATH = path.join(CERT_DIR, "localhost-key.pem");
export const CERT_PATH = path.join(CERT_DIR, "localhost-cert.pem");

/** Create the certificate unless one is already there. */
export function ensureCert() {
  if (existsSync(KEY_PATH) && existsSync(CERT_PATH)) {
    return { key: KEY_PATH, cert: CERT_PATH };
  }

  mkdirSync(CERT_DIR, { recursive: true });
  execFileSync(
    "openssl",
    [
      "req",
      "-x509",
      "-newkey",
      "rsa:2048",
      "-nodes",
      "-keyout",
      KEY_PATH,
      "-out",
      CERT_PATH,
      "-days",
      "365",
      "-subj",
      "/CN=localhost",
      // Browsers ignore the legacy CN and read the SAN, so a certificate without one is
      // rejected before ignoreHTTPSErrors even gets a say in some engines.
      "-addext",
      "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1",
    ],
    { stdio: "ignore" },
  );

  return { key: KEY_PATH, cert: CERT_PATH };
}

if (import.meta.filename === process.argv[1]) {
  const { cert } = ensureCert();
  console.log(`e2e certificate ready: ${cert}`);
}
