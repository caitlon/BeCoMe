import { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import i18n from '@/i18n'
import { User } from '@/types/api'

/**
 * Mock AuthContext value for testing.
 * Allows controlling auth state in component tests.
 */
export interface MockAuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: ReturnType<typeof import('vitest').vi.fn>;
  register: ReturnType<typeof import('vitest').vi.fn>;
  logout: ReturnType<typeof import('vitest').vi.fn>;
  refreshUser: ReturnType<typeof import('vitest').vi.fn>;
}

/**
 * Extended render options for testing.
 */
export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: MemoryRouterProps['initialEntries'];
  wrapper?: RenderOptions['wrapper'];
}

function AllTheProviders({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <I18nextProvider i18n={i18n}>
        {children}
      </I18nextProvider>
    </MemoryRouter>
  )
}

/**
 * Creates a wrapper with custom router initial entries.
 */
function createWrapper(initialEntries?: MemoryRouterProps['initialEntries']) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter
        initialEntries={initialEntries}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <I18nextProvider i18n={i18n}>
          {children}
        </I18nextProvider>
      </MemoryRouter>
    )
  }
}

/**
 * Custom render function with providers.
 * Use initialEntries to set the initial route.
 */
const customRender = (
  ui: ReactElement,
  options?: CustomRenderOptions
) => {
  const { initialEntries, ...renderOptions } = options ?? {}
  const wrapper = renderOptions.wrapper ?? (initialEntries ? createWrapper(initialEntries) : AllTheProviders)
  return render(ui, { wrapper, ...renderOptions })
}

export * from '@testing-library/react'
export { customRender as render }
