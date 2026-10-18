import { render, screen } from '@tests/utils'
import { MemoryRouter, Routes, Route } from 'react-router'
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

  it('renders children when unauthenticated', () => {
    renderAtLogin('unauthenticated')

    expect(screen.getByText('Login Form')).toBeInTheDocument()
    expect(screen.queryByText('Projects Page')).not.toBeInTheDocument()
  })

  it('renders children while the session is loading, so a form submit is not unmounted', () => {
    renderAtLogin('loading')

    expect(screen.getByText('Login Form')).toBeInTheDocument()
    expect(screen.queryByText('Projects Page')).not.toBeInTheDocument()
  })

  it('renders children when the service is unavailable', () => {
    renderAtLogin('serviceUnavailable')

    expect(screen.getByText('Login Form')).toBeInTheDocument()
    expect(screen.queryByText('Projects Page')).not.toBeInTheDocument()
  })
})
