import { render, screen } from '@tests/utils'
import { MemoryRouter, Routes, Route } from 'react-router'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import * as AuthContext from '@/contexts/AuthContext'
import { createUser } from '@tests/factories/user'

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}))

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
