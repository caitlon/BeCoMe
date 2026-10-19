import { render, screen, waitFor } from '@tests/utils'
import { MemoryRouter, Routes, Route, RouterProvider, createMemoryRouter, useLocation } from 'react-router'
import { describe, it, expect, vi } from 'vitest'
import { GuestRoute } from '@/components/auth/GuestRoute'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
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
  setCurrentUser: vi.fn(),
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

  describe('returning to the page the visitor came from', () => {
    function LocationProbe() {
      const { pathname, search, hash } = useLocation()
      return <div>{`at ${pathname}${search}${hash}`}</div>
    }

    function renderLoginWithFrom(from: unknown) {
      vi.mocked(AuthContext.useAuth).mockReturnValue(session('authenticated'))

      render(
        <MemoryRouter initialEntries={[{ pathname: '/login', state: { from } }]}>
          <Routes>
            <Route
              path="/login"
              element={
                <GuestRoute>
                  <div>Login Form</div>
                </GuestRoute>
              }
            />
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>,
        { wrapper: ({ children }) => children }
      )
    }

    it('lands on the internal page, with its query and hash', () => {
      renderLoginWithFrom({ pathname: '/projects/42', search: '?tab=results', hash: '#x' })

      expect(screen.getByText('at /projects/42?tab=results#x')).toBeInTheDocument()
    })

    it('drops a search and a hash that are not strings', () => {
      renderLoginWithFrom({ pathname: '/projects/42', search: { a: 1 }, hash: 7 })

      expect(screen.getByText('at /projects/42')).toBeInTheDocument()
    })

    it('goes to the projects page when no page was remembered', () => {
      renderLoginWithFrom(undefined)

      expect(screen.getByText('at /projects')).toBeInTheDocument()
    })

    it.each([
      ['a protocol-relative URL', { pathname: '//evil.example' }],
      ['a backslash after the slash', { pathname: '/\\evil.example' }],
      ['a tab that browsers strip before parsing', { pathname: '/\t/evil.example' }],
      ['a newline that browsers strip before parsing', { pathname: '/\n/evil.example' }],
      ['an absolute URL', { pathname: 'https://evil.example' }],
      ['a URL that does not parse', { pathname: '//evil.example:99999' }],
      ['a dot segment that normalizes to a protocol-relative path', { pathname: '/.//evil.example' }],
      ['a parent segment that normalizes to a protocol-relative path', { pathname: '/projects/..//evil.example' }],
      ['a relative path', { pathname: 'projects/42' }],
      ['an empty path', { pathname: '' }],
      ['a pathname that is not a string', { pathname: 42 }],
      ['a missing pathname', {}],
      ['a plain string', '/projects/42'],
      ['null', null],
    ])('goes to the projects page for %s', (_label, from) => {
      renderLoginWithFrom(from)

      expect(screen.getByText('at /projects')).toBeInTheDocument()
    })
  })

  it('sends a visitor back to the protected page after signing in', () => {
    let current = session('unauthenticated')
    vi.mocked(AuthContext.useAuth).mockImplementation(() => current)

    const tree = () => (
      <MemoryRouter initialEntries={['/projects/42']}>
        <Routes>
          <Route
            path="/projects/:id"
            element={
              <ProtectedRoute>
                <div>Project Page</div>
              </ProtectedRoute>
            }
          />
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
      </MemoryRouter>
    )

    const { rerender } = render(tree(), { wrapper: ({ children }) => children })
    expect(screen.getByText('Login Form')).toBeInTheDocument()

    current = session('authenticated')
    rerender(tree())

    expect(screen.getByText('Project Page')).toBeInTheDocument()
    expect(screen.queryByText('Projects Page')).not.toBeInTheDocument()
  })
})
