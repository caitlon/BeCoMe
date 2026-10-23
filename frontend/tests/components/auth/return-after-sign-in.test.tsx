import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route, useLocation } from 'react-router'
import { render } from '@tests/utils'
import { createUser } from '@tests/factories/user'
import { AuthProvider } from '@/contexts/AuthContext'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { GuestRoute } from '@/components/auth/GuestRoute'
import Login from '@/pages/Login'
import { UnauthorizedError } from '@/lib/errors'

// Only the transport is mocked: the session probe, the sign-in call and the
// expiry hook AuthProvider registers.
const mockGetCurrentUser = vi.fn()
const mockLogin = vi.fn()
vi.mock('@/lib/api', () => ({
  api: {
    getCurrentUser: (isAuthProbe: boolean) => mockGetCurrentUser(isAuthProbe),
    login: (email: string, password: string, turnstileToken: string | null) =>
      mockLogin(email, password, turnstileToken),
    setOnSessionExpired: vi.fn(),
  },
}))

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

function ProjectPage() {
  const { pathname, search, hash } = useLocation()
  return <div>{`project page at ${pathname}${search}${hash}`}</div>
}

describe('returning to the requested page after signing in', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('takes a visitor from the sign-in form back to the page they asked for', async () => {
    const user = userEvent.setup()
    mockGetCurrentUser
      .mockRejectedValueOnce(new UnauthorizedError())
      .mockResolvedValue(createUser({ id: '1' }))
    mockLogin.mockResolvedValue(undefined)

    render(
      <AuthProvider>
        <Routes>
          <Route
            path="/projects/:id"
            element={
              <ProtectedRoute>
                <ProjectPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/login"
            element={
              <GuestRoute>
                <Login />
              </GuestRoute>
            }
          />
          <Route path="/projects" element={<div>projects list</div>} />
        </Routes>
      </AuthProvider>,
      { initialEntries: ['/projects/42?tab=results#x'] }
    )

    await user.type(await screen.findByPlaceholderText('you@example.com'), 'test@example.com')
    await user.type(screen.getByPlaceholderText('Enter your password'), 'password123')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText('project page at /projects/42?tab=results#x')).toBeInTheDocument()
    })
    expect(screen.queryByText('projects list')).not.toBeInTheDocument()
    expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123', null)
  })
})
