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

// happy-dom 20.12.0 made `Animation.cancel()` reject the animation's `finished` promise with an
// AbortError, as the Web Animations spec says. framer-motion cancels animations when a component
// unmounts and never reads `finished`, so each cancel became an unhandled rejection that failed
// the vitest run while every test passed. Browsers mark that rejection handled; do the same here.
// Only the promise that `cancel()` is about to reject is touched, so unrelated rejections still
// surface, and code that awaits `finished` still sees the AbortError.
const originalCancel = Animation.prototype.cancel
Animation.prototype.cancel = function cancel(this: Animation) {
  this.finished.catch(() => {})
  originalCancel.call(this)
}

afterEach(() => {
  cleanup()
})
