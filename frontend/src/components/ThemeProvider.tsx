import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

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
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(storageKey) as Theme) || defaultTheme
  )
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolveTheme(theme))

  useEffect(() => {
    const root = globalThis.document.documentElement

    const applyResolvedTheme = (resolved: ResolvedTheme) => {
      root.classList.remove("light", "dark")
      root.classList.add(resolved)
      setResolvedTheme(resolved)
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
  }, [theme])

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
