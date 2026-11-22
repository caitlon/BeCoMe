import { createContext, startTransition, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react"
import { isHydrating } from "@/lib/hydration"

type Theme = "dark" | "light" | "system"
type ResolvedTheme = "dark" | "light"

type ThemeProviderProps = {
  readonly children: React.ReactNode
  readonly defaultTheme?: Theme
  readonly storageKey?: string
}

type ThemeProviderState = {
  theme: Theme
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
}

function getSystemTheme(): ResolvedTheme {
  /* v8 ignore next 3 */
  return typeof globalThis.matchMedia === "function"
    && globalThis.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light"
}

/**
 * The stored choice, or null when there is none or storage cannot be read. A
 * server has no window, and newer Node versions expose a localStorage global
 * that can throw when accessed without --localstorage-file, so the check is for
 * the window, not for the global.
 */
function readStoredTheme(storageKey: string): Theme | null {
  if (typeof window === "undefined") return null
  try {
    return window.localStorage.getItem(storageKey) as Theme | null
  } catch {
    return null
  }
}

function resolveTheme(theme: Theme): ResolvedTheme {
  return theme === "system" ? getSystemTheme() : theme
}

const initialState: ThemeProviderState = {
  theme: "system",
  resolvedTheme: "light",
  setTheme: () => null,
}

const ThemeProviderContext = createContext<ThemeProviderState>(initialState)

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "vite-ui-theme",
  ...props
}: ThemeProviderProps) {
  // While hydrating, the first render must match the server HTML, which was made
  // without a stored choice and without a colour-scheme preference, so it saw
  // defaultTheme resolved as light. The real values are applied after hydration,
  // inside startTransition, so React keeps the server markup.
  const [hydrating] = useState(isHydrating)
  const [theme, setTheme] = useState<Theme>(
    () => (hydrating ? null : readStoredTheme(storageKey)) || defaultTheme
  )
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    hydrating && theme === "system" ? "light" : resolveTheme(theme)
  )

  // The stored choice that hydration left out of state, until the transition below lands it.
  const pendingTheme = useRef<Theme | null>(null)

  useEffect(() => {
    if (!hydrating) return
    const stored = readStoredTheme(storageKey)
    if (stored && stored !== defaultTheme) {
      pendingTheme.current = stored
      startTransition(() => setTheme(stored))
    }
  }, [hydrating, storageKey, defaultTheme])

  useEffect(() => {
    const root = globalThis.document.documentElement

    // Put the stored choice's class on the page right away, so the pre-hydration
    // default does not flash for the one render before the transition commits.
    if (pendingTheme.current && pendingTheme.current !== theme) {
      root.classList.remove("light", "dark")
      root.classList.add(resolveTheme(pendingTheme.current))
      return
    }
    pendingTheme.current = null

    const applyResolvedTheme = (resolved: ResolvedTheme) => {
      root.classList.remove("light", "dark")
      root.classList.add(resolved)
      if (hydrating) {
        startTransition(() => setResolvedTheme(resolved))
      } else {
        setResolvedTheme(resolved)
      }
    }

    if (theme !== "system") {
      applyResolvedTheme(theme)
      return
    }

    applyResolvedTheme(getSystemTheme())

    /* v8 ignore next 3 */
    if (typeof globalThis.matchMedia !== "function") {
      return
    }

    // Keep resolvedTheme (and the applied .dark/.light class) in sync when
    // the OS color scheme changes while the user's preference is "system".
    const mediaQuery = globalThis.matchMedia("(prefers-color-scheme: dark)")
    const handleChange = () => applyResolvedTheme(mediaQuery.matches ? "dark" : "light")

    mediaQuery.addEventListener("change", handleChange)
    return () => mediaQuery.removeEventListener("change", handleChange)
  }, [theme, hydrating])

  const handleSetTheme = useCallback((newTheme: Theme) => {
    localStorage.setItem(storageKey, newTheme)
    setTheme(newTheme)
  }, [storageKey])

  const value = useMemo(() => ({
    theme,
    resolvedTheme,
    setTheme: handleSetTheme,
  }), [theme, resolvedTheme, handleSetTheme])

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext)

  /* v8 ignore next 2 */
  if (context === undefined)
    throw new Error("useTheme must be used within a ThemeProvider")

  return context
}
