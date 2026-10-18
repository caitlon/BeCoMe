import { render, screen, waitFor } from '@tests/utils'
import { MemoryRouter, Routes, Route, RouterProvider, createMemoryRouter } from 'react-router'
import { describe, it, expect, vi } from 'vitest'
import { GuestRoute } from '@/components/auth/GuestRoute'
import * as AuthContext from '@/contexts/AuthContext'
import { createUser } from '@tests/factories/user'

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}))

type SessionStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'serviceUnavailable'

const session = (status: SessionStatus) => ({
  status,
  isLoading: status === 'loading',
  isAuthenticated: status === 'authenticated',
  isServiceUnavailable: status === 'serviceUnavailable',
  user: status === 'authenticated' ? createUser({ id: '1' }) : null,
  login: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
})

function renderAtLogin(status: SessionStatus) {
  vi.mocked(AuthContext.useAuth).mockReturnValue(session(status))

  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route
          path="/login"
          element={
            <GuestRoute>
              <div>Login Form</div>
            </GuestRoute>
          }
        />
        <Route path="/projects" element={<div>Projects Page</div>} />
      </Routes>
    </MemoryRouter>,
    { wrapper: ({ children }) => children }
  )
}

describe('GuestRoute', () => {
  it('redirects a signed-in visitor to the projects page', () => {
    renderAtLogin('authenticated')

    expect(screen.queryByText('Login Form')).not.toBeInTheDocument()
    expect(screen.getByText('Projects Page')).toBeInTheDocument()
  })

  // Loading renders the page too: login() re-probes the session during a form
  // submit, so unmounting the form at that moment would break the submit.
  it.each<SessionStatus>(['unauthenticated', 'loading', 'serviceUnavailable'])(
    'renders children when the session is %s',
    (status) => {
      renderAtLogin(status)

      expect(screen.getByText('Login Form')).toBeInTheDocument()
      expect(screen.queryByText('Projects Page')).not.toBeInTheDocument()
    }
  )

  it('replaces the history entry instead of pushing a new one', async () => {
    vi.mocked(AuthContext.useAuth).mockReturnValue(session('authenticated'))
    const router = createMemoryRouter(
      [
        { path: '/', element: <div>Home</div> },
        {
          path: '/login',
          element: (
            <GuestRoute>
              <div>login form</div>
            </GuestRoute>
          ),
        },
        { path: '/projects', element: <div>Projects Page</div> },
      ],
      { initialEntries: ['/', '/login'], initialIndex: 1 }
    )

    render(<RouterProvider router={router} />, { wrapper: ({ children }) => children })

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/projects')
      expect(router.state.historyAction).toBe('REPLACE')
    })
  })
})
