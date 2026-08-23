import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

// The e2e suite serves the app over HTTPS (see frontend/scripts/e2e-cert.mjs for why the
// session cookies require it). Everyday `npm run dev` stays on plain HTTP.
//
// The switch is this environment variable, set by `npm run dev:e2e`, rather than the mere
// presence of the certificate: keying it on the file would mean that running e2e once
// silently turns every later `npm run dev` into an HTTPS server, and the developer who
// wonders why their browser now warns about the certificate has nothing to grep for.
const certDir = path.resolve(import.meta.dirname, ".certs");
const keyFile = path.join(certDir, "localhost-key.pem");
const certFile = path.join(certDir, "localhost-cert.pem");
const https = process.env.E2E_HTTPS
  ? { key: fs.readFileSync(keyFile), cert: fs.readFileSync(certFile) }
  : undefined;

export default defineConfig({
  server: {
    host: "::",
    port: 8080,
    https,
    proxy: {
      "/api/v1": {
        // Plain HTTP on purpose even when the dev server itself is on TLS: this hop stays
        // inside the machine, and terminating TLS here would mean the API needs its own
        // certificate for a connection no browser ever sees. What the browser sees -- and
        // what decides whether a Secure cookie is stored -- is the connection above.
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
});
