import { Suspense, use } from 'react'
import { act, render, screen } from '@tests/utils'
import { MemoryRouter, Routes, Route } from 'react-router'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import * as AuthContext from '@/contexts/AuthContext'
import { createUser } from '@tests/factories/user'
import { PageLoader } from '@/components/PageLoader'

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}))

const neverLoaded = new Promise<never>(() => {})

function LazyPage(): never {
  return use(neverLoaded)
}

const session = (isLoading: boolean) => ({
  status: isLoading ? ('loading' as const) : ('authenticated' as const),
  isLoading,
  isAuthenticated: !isLoading,
  isServiceUnavailable: false,
  user: isLoading ? null : createUser({ id: '1' }),
  login: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
})

describe('ProtectedRoute', () => {
  it('shows loading spinner when isLoading is true', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      status: 'loading',
      isLoading: true,
      isAuthenticated: false,
      isServiceUnavailable: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    )

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
  })

  it('keeps a focusable main#main-content on screen while the session is checked', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      status: 'loading',
      isLoading: true,
      isAuthenticated: false,
      isServiceUnavailable: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    )

    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('id', 'main-content')
    expect(main).toHaveAttribute('tabindex', '-1')
  })

  it('keeps one visible main#main-content while the protected page itself loads', async () => {
    const tree = () => (
      <Suspense fallback={<PageLoader />}>
        <ProtectedRoute>
          <LazyPage />
        </ProtectedRoute>
      </Suspense>
    )

    // As in App: the session check shows a placeholder, then the page suspends.
    vi.mocked(AuthContext.useAuth).mockReturnValue(session(true))
    const { rerender, container } = render(tree())
    vi.mocked(AuthContext.useAuth).mockReturnValue(session(false))
    rerender(tree())
    // React holds back a fallback that replaces content already on screen, for up to 300 ms.
    await act(() => new Promise((resolve) => setTimeout(resolve, 400)))

    const mains = container.querySelectorAll('main#main-content')
    expect(mains).toHaveLength(1)
    expect(mains[0]).toBeVisible()
  })

  it('leaves a page that suspends to the outer boundary when it mounted signed in', () => {
    // A client-side navigation: the outer boundary keeps the previous page on screen, which
    // a boundary of ProtectedRoute's own would replace with a full-screen placeholder.
    vi.mocked(AuthContext.useAuth).mockReturnValue(session(false))

    render(
      <Suspense fallback={<p>outer fallback</p>}>
        <ProtectedRoute>
          <LazyPage />
        </ProtectedRoute>
      </Suspense>
    )

    expect(screen.getByText('outer fallback')).toBeInTheDocument()
    expect(screen.queryByRole('main')).not.toBeInTheDocument()
  })

  it('keeps a main#main-content next to the redirect while the login page loads', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({ ...session(false), isAuthenticated: false, user: null })

    const { container } = render(
      <MemoryRouter initialEntries={['/protected']}>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route
              path="/protected"
              element={
                <ProtectedRoute>
                  <div>Protected Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<LazyPage />} />
          </Routes>
        </Suspense>
      </MemoryRouter>,
      { wrapper: ({ children }) => children }
    )

    const mains = container.querySelectorAll('main#main-content')
    expect(mains).toHaveLength(1)
    expect(mains[0]).toBeVisible()
  })

  it('renders children when authenticated', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      status: 'authenticated',
      isLoading: false,
      isAuthenticated: true,
      isServiceUnavailable: false,
      user: createUser({ id: '1', email: 'test@example.com', first_name: 'Test' }),
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('redirects to login when not authenticated', () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      status: 'unauthenticated',
      isLoading: false,
      isAuthenticated: false,
      isServiceUnavailable: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/login"
            element={<div>Login Page</div>}
          />
        </Routes>
      </MemoryRouter>,
      { wrapper: ({ children }) => children }
    )

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })

  it('shows a retry panel instead of redirecting when the service is unavailable', () => {
    const refreshUser = vi.fn()
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      status: 'serviceUnavailable',
      isLoading: false,
      isAuthenticated: false,
      isServiceUnavailable: true,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser,
    })

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>,
      { wrapper: ({ children }) => children }
    )

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('calls refreshUser when the retry button is clicked', async () => {
    const user = userEvent.setup()
    const refreshUser = vi.fn()
    vi.mocked(AuthContext.useAuth).mockReturnValue({
      status: 'serviceUnavailable',
      isLoading: false,
      isAuthenticated: false,
      isServiceUnavailable: true,
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser,
    })

    render(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    )

    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(refreshUser).toHaveBeenCalledTimes(1)
  })
})
