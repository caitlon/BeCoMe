import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    // https, because the session cookies carry the __Host- prefix and happy-dom enforces
    // the rule browsers do: such a cookie is only stored on a secure origin. On the
    // default http://localhost the assignment is silently dropped, and a test reading it
    // back sees undefined, which looks like a bug in the client rather than the
    // document refusing the cookie.
    environmentOptions: { happyDOM: { url: 'https://localhost:8080' } },
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.d.ts',
        'src/types/**',
        'src/components/ui/**',
        'src/main.tsx',
        'src/components/onboarding/index.ts',
        'src/components/forms/index.ts',
      ],
      thresholds: {
        statements: 98,
        branches: 95,
        functions: 97,
        lines: 98,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@tests': path.resolve(__dirname, './tests'),
    },
  },
})
