import { ReactNode } from 'react'
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/hooks/use-toast'
import { api } from '@/lib/api'
import { UnauthorizedError, ForbiddenError, ServerError, NetworkError } from '@/lib/errors'
import { User } from '@/types/api'
import i18n from '@/i18n'
import { createUser } from '@tests/factories/user'

function AuthTestProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <I18nextProvider i18n={i18n}>
        <AuthProvider>{children}</AuthProvider>
      </I18nextProvider>
    </QueryClientProvider>
  )
}

vi.mock('@/lib/api', () => ({
  api: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    setOnSessionExpired: vi.fn(),
  },
}))

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('throws error when useAuth is used outside AuthProvider', () => {
    const consoleErrorSpy = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    try {
      expect(() => renderHook(() => useAuth())).toThrow(
        'useAuth must be used within an AuthProvider'
      );
    } finally {
      consoleErrorSpy.mockRestore();
    }
  })

  it('sets isAuthenticated to true when user exists', async () => {
    const mockUser = createUser({ id: '1', email: 'test@example.com', first_name: 'Test' })
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.status).toBe('authenticated')
    expect(result.current.user).toEqual(mockUser)
  })

  it('sets isAuthenticated to false when there is no active session', async () => {
    vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.status).toBe('unauthenticated')
    expect(result.current.user).toBeNull()
  })

  it('treats a forbidden probe the same as an unauthenticated session', async () => {
    vi.mocked(api.getCurrentUser).mockRejectedValue(new ForbiddenError())

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.status).toBe('unauthenticated')
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('sets status to serviceUnavailable on a ServerError, without treating it as logged out', async () => {
    vi.mocked(api.getCurrentUser).mockRejectedValue(new ServerError())

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.status).toBe('serviceUnavailable')
    })

    expect(result.current.isLoading).toBe(false)
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.isServiceUnavailable).toBe(true)
    expect(result.current.user).toBeNull()
  })

  it('sets status to serviceUnavailable on a NetworkError', async () => {
    vi.mocked(api.getCurrentUser).mockRejectedValue(new NetworkError())

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.status).toBe('serviceUnavailable')
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.isServiceUnavailable).toBe(true)
  })

  it('refreshUser flips status to loading before the request settles, for Retry feedback', async () => {
    vi.mocked(api.getCurrentUser).mockRejectedValueOnce(new ServerError())

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.status).toBe('serviceUnavailable')
    })

    let resolveRetry!: (user: User) => void
    vi.mocked(api.getCurrentUser).mockImplementationOnce(
      () => new Promise<User>((resolve) => { resolveRetry = resolve })
    )

    let retryPromise: Promise<void>
    act(() => {
      retryPromise = result.current.refreshUser()
    })

    expect(result.current.status).toBe('loading')

    const mockUser = createUser({ id: '1', email: 'test@example.com', first_name: 'Test' })
    await act(async () => {
      resolveRetry(mockUser)
      await retryPromise!
    })

    expect(result.current.status).toBe('authenticated')
  })

  it('login calls api.login and refreshes user', async () => {
    const mockUser = createUser({ id: '1', email: 'test@example.com', first_name: 'Test' })
    vi.mocked(api.login).mockResolvedValue({ access_token: 'new-token', token_type: 'bearer' })
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.login('test@example.com', 'password')
    })

    expect(api.login).toHaveBeenCalledWith('test@example.com', 'password')
  })

  it('logout clears user and calls api.logout', async () => {
    const mockUser = createUser({ id: '1', email: 'test@example.com', first_name: 'Test' })
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    await act(async () => {
      await result.current.logout()
    })

    expect(api.logout).toHaveBeenCalled()
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.status).toBe('unauthenticated')
  })

  it('clears the local session and propagates the failure when the logout request fails', async () => {
    // A server that refuses the sign-out must not leave the user signed in. This is
    // what a cookie-authenticated logout looked like on every deploy: the SPA could
    // not read the csrf_token cookie, so the request came back 403. Clearing the
    // local session is not enough on its own though -- a caller that never learns
    // the server-side session survived would show the exact same success state as
    // a real sign-out, which is worse than an error on a shared machine.
    const mockUser = createUser({ id: '1', email: 'test@example.com', first_name: 'Test' })
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)
    // Once, not for the rest of the file: clearAllMocks resets recorded calls but
    // leaves an implementation in place, and the cases after this one expect a
    // logout that succeeds.
    vi.mocked(api.logout).mockRejectedValueOnce(new ForbiddenError('CSRF token missing or invalid'))

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    // Catch inside act() rather than asserting on the rejected act() promise itself:
    // act() only flushes the state updates queued before the throw when its own
    // callback settles without rejecting, so the throw is captured here and
    // checked on the side, letting the surrounding act() see a normal resolution.
    let caughtError: unknown
    await act(async () => {
      try {
        await result.current.logout()
      } catch (err) {
        caughtError = err
      }
    })

    expect(caughtError).toBeInstanceOf(Error)
    expect((caughtError as Error).message).toBe('CSRF token missing or invalid')
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.status).toBe('unauthenticated')
  })

  it('drops cached queries on logout so the next account cannot see them', async () => {
    const mockUser = createUser({ id: '1', email: 'test@example.com', first_name: 'Test' })
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <AuthProvider>{children}</AuthProvider>
        </I18nextProvider>
      </QueryClientProvider>
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    queryClient.setQueryData(['projects'], [{ id: 'p1' }])

    await act(async () => {
      await result.current.logout()
    })

    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
  })

  it('clears the user when the session probe fails', async () => {
    vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError('Token expired'))

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('propagates login error to caller', async () => {
    vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthTestProviders,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    vi.mocked(api.login).mockRejectedValue(new Error('Invalid credentials'))

    await expect(
      act(async () => {
        await result.current.login('bad@example.com', 'wrong')
      })
    ).rejects.toThrow('Invalid credentials')
  })

  describe('onSessionExpired bridge', () => {
    it('registers a callback with the api client on mount and clears it on unmount', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())

      const { unmount } = renderHook(() => useAuth(), {
        wrapper: AuthTestProviders,
      })

      await waitFor(() => {
        expect(api.setOnSessionExpired).toHaveBeenCalledWith(expect.any(Function))
      })

      unmount()

      expect(api.setOnSessionExpired).toHaveBeenLastCalledWith(null)
    })

    it('clears the user, flips to unauthenticated, and shows a toast when the session expires', async () => {
      const mockUser = createUser({ id: '1', email: 'test@example.com', first_name: 'Test' })
      vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

      const { result } = renderHook(
        () => ({ auth: useAuth(), toastState: useToast() }),
        { wrapper: AuthTestProviders }
      )

      await waitFor(() => {
        expect(result.current.auth.isAuthenticated).toBe(true)
      })

      const onSessionExpired = vi.mocked(api.setOnSessionExpired).mock.calls[0][0]

      act(() => {
        onSessionExpired?.()
      })

      await waitFor(() => {
        expect(result.current.auth.isAuthenticated).toBe(false)
      })

      expect(result.current.auth.user).toBeNull()
      expect(result.current.auth.status).toBe('unauthenticated')
      expect(result.current.toastState.toasts[0]).toMatchObject({
        title: 'Session expired',
        description: 'Your session has expired. Please sign in again.',
        variant: 'destructive',
      })
    })
  })
})
