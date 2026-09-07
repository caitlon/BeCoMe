import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { Storage } from 'happy-dom'
import { afterEach } from 'vitest'

// Node 26 puts its own `localStorage` accessor on `globalThis`, and that accessor returns
// `undefined` unless the process was started with `--localstorage-file`, because Node backs
// localStorage with a file. It shadows the Storage happy-dom would otherwise expose, so
// `localStorage` reads as undefined inside tests while `sessionStorage`, whose Node accessor
// needs no flag, keeps working. The asymmetry is what makes this look like a happy-dom bug.
//
// Restore a real DOM Storage under the name. Guarded, so it does nothing wherever the global
// already works, which is the case on the Node version CI runs.
if (typeof globalThis.localStorage === 'undefined') {
  Object.defineProperty(globalThis, 'localStorage', {
    value: new Storage(),
    configurable: true,
    writable: true,
  })
}

afterEach(() => {
  cleanup()
})
