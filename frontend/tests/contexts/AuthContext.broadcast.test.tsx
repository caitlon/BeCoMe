import { ReactNode } from 'react'
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import { AuthProvider, useAuth, registerSignOutListener } from '@/contexts/AuthContext'
import { useToast } from '@/hooks/use-toast'
import { api } from '@/lib/api'
import { ForbiddenError, RateLimitError, UnauthorizedError } from '@/lib/errors'
import i18n from '@/i18n'
import type { User } from '@/types/api'
import { createUser } from '@tests/factories/user'
import { FakeBroadcastChannel } from '@tests/support/fake-broadcast-channel'

vi.mock('@/lib/api', () => ({
  api: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    setOnSessionExpired: vi.fn(),
  },
}))

const CHANNEL = 'become-auth'

// One "tab" is one AuthProvider with a query cache of its own, as in a real browser.
function mountTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <AuthProvider>{children}</AuthProvider>
      </I18nextProvider>
    </QueryClientProvider>
  )
  const view = renderHook(() => ({ auth: useAuth(), toasts: useToast().toasts }), { wrapper })
  return { ...view, queryClient }
}

// A request the test settles by hand, to put two probes in flight at once.
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

// A bare channel standing in for another tab: what it posts reaches the tab under test, and
// what the tab posts lands in `received`.
function otherTab() {
  const channel = new FakeBroadcastChannel(CHANNEL)
  const received: unknown[] = []
  channel.onmessage = (event) => received.push(event.data)
  return { channel, received }
}

describe('AuthContext across tabs', () => {
  const unsubscribers: Array<() => void> = []

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.logout).mockResolvedValue(undefined)
    FakeBroadcastChannel.reset()
    vi.stubGlobal('BroadcastChannel', FakeBroadcastChannel)
  })

  afterEach(() => {
    unsubscribers.splice(0).forEach((unsubscribe) => unsubscribe())
    vi.unstubAllGlobals()
  })

  async function signedInTab() {
    vi.mocked(api.getCurrentUser).mockResolvedValue(createUser({ id: '1' }))
    const tab = mountTab()
    await waitFor(() => expect(tab.result.current.auth.isAuthenticated).toBe(true))
    return tab
  }

  describe('sending', () => {
    it('posts signed-out on an explicit logout', async () => {
      const tab = await signedInTab()
      const other = otherTab()

      await act(async () => {
        await tab.result.current.auth.logout()
      })

      expect(other.received).toEqual([{ type: 'signed-out' }])
    })

    it('posts signed-out on a logout the server refused, since the local session is gone anyway', async () => {
      const tab = await signedInTab()
      const other = otherTab()
      vi.mocked(api.logout).mockRejectedValueOnce(new ForbiddenError('CSRF token missing or invalid'))

      await act(async () => {
        await tab.result.current.auth.logout().catch(() => undefined)
      })

      expect(other.received).toEqual([{ type: 'signed-out' }])
    })

    it('posts signed-out when the session expires', async () => {
      const tab = await signedInTab()
      const other = otherTab()
      const onSessionExpired = vi.mocked(api.setOnSessionExpired).mock.lastCall![0]

      act(() => {
        onSessionExpired?.()
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(other.received).toEqual([{ type: 'signed-out' }])
    })

    it('posts nothing when the session expires in a tab that holds no user', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())
      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.status).toBe('unauthenticated'))
      const other = otherTab()
      const onSessionExpired = vi.mocked(api.setOnSessionExpired).mock.lastCall![0]

      act(() => {
        onSessionExpired?.()
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(other.received).toEqual([])
    })

    it.each([
      ['401', () => new UnauthorizedError()],
      ['403', () => new ForbiddenError('nope')],
    ])('posts signed-out when a probe of a signed-in tab is refused with %s', async (_label, makeError) => {
      const tab = await signedInTab()
      const other = otherTab()
      vi.mocked(api.getCurrentUser).mockRejectedValueOnce(makeError())

      await act(async () => {
        await tab.result.current.auth.refreshUser()
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(other.received).toEqual([{ type: 'signed-out' }])
    })

    it('posts nothing and shows the service as unavailable when a probe is throttled with 429', async () => {
      const tab = await signedInTab()
      const other = otherTab()
      vi.mocked(api.getCurrentUser).mockRejectedValueOnce(new RateLimitError('Too many requests', 30))

      await act(async () => {
        await tab.result.current.auth.refreshUser()
      })

      expect(tab.result.current.auth.status).toBe('serviceUnavailable')
      expect(other.received).toEqual([])
    })

    it('posts nothing when an anonymous tab is told so by its first probe', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())
      const other = otherTab()

      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.status).toBe('unauthenticated'))

      expect(other.received).toEqual([])
    })

    it('posts signed-in after a successful login, and nothing after a refused one', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())
      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.status).toBe('unauthenticated'))
      const other = otherTab()

      vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))
      await act(async () => {
        await tab.result.current.auth.login('a@example.com', 'wrong').catch(() => undefined)
      })
      expect(other.received).toEqual([])

      vi.mocked(api.login).mockResolvedValue({ access_token: 't', token_type: 'bearer' })
      vi.mocked(api.getCurrentUser).mockResolvedValue(createUser({ id: '1' }))
      await act(async () => {
        await tab.result.current.auth.login('a@example.com', 'pw')
      })

      expect(other.received).toEqual([{ type: 'signed-in' }])
      expect(tab.result.current.auth.isAuthenticated).toBe(true)
    })

    it('puts only a type in a message, never the user, an email or a token', async () => {
      const tab = await signedInTab()
      vi.mocked(api.login).mockResolvedValue({ access_token: 'secret-token', token_type: 'bearer' })

      await act(async () => {
        await tab.result.current.auth.login('a@example.com', 'pw')
        await tab.result.current.auth.logout()
      })

      expect(FakeBroadcastChannel.posted).toHaveLength(2)
      for (const message of FakeBroadcastChannel.posted) {
        expect(Object.keys(message as object)).toEqual(['type'])
      }
      expect(JSON.stringify(FakeBroadcastChannel.posted)).not.toMatch(/example\.com|secret-token|"1"/)
    })

    it('closes its channel when the provider unmounts', async () => {
      const tab = await signedInTab()
      expect(FakeBroadcastChannel.openCount(CHANNEL)).toBe(1)

      tab.unmount()

      expect(FakeBroadcastChannel.openCount(CHANNEL)).toBe(0)
    })
  })

  describe('receiving', () => {
    it('signs a second tab out when the first one logs out, with no request of its own', async () => {
      vi.mocked(api.getCurrentUser).mockResolvedValue(createUser({ id: '1' }))
      const first = mountTab()
      const second = mountTab()
      await waitFor(() => {
        expect(first.result.current.auth.isAuthenticated).toBe(true)
        expect(second.result.current.auth.isAuthenticated).toBe(true)
      })
      second.queryClient.setQueryData(['projects'], [{ id: 'p1' }])
      const listener = vi.fn()
      unsubscribers.push(registerSignOutListener(listener))
      vi.mocked(api.getCurrentUser).mockClear()

      await act(async () => {
        await first.result.current.auth.logout()
      })

      expect(second.result.current.auth.status).toBe('unauthenticated')
      expect(second.result.current.auth.user).toBeNull()
      expect(second.result.current.auth.isAuthenticated).toBe(false)
      expect(second.queryClient.getQueryData(['projects'])).toBeUndefined()
      // Once for the tab that logged out, once for the one that heard about it.
      expect(listener).toHaveBeenCalledTimes(2)
      expect(api.logout).toHaveBeenCalledTimes(1)
      expect(api.getCurrentUser).not.toHaveBeenCalled()
    })

    it('shows no toast in the tab that heard about the sign-out', async () => {
      const tab = await signedInTab()
      // The toast store outlives a test, so count what is there before the message.
      const toastsBefore = tab.result.current.toasts.length

      act(() => {
        otherTab().channel.postMessage({ type: 'signed-out' })
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(tab.result.current.toasts).toHaveLength(toastsBefore)
    })

    it('notifies the sign-out listeners only after the query cache is cleared', async () => {
      const tab = await signedInTab()
      tab.queryClient.setQueryData(['projects'], [{ id: 'p1' }])
      let cacheSeenByListener: unknown = 'not called'
      unsubscribers.push(
        registerSignOutListener(() => {
          cacheSeenByListener = tab.queryClient.getQueryData(['projects'])
        })
      )

      act(() => {
        otherTab().channel.postMessage({ type: 'signed-out' })
      })

      expect(cacheSeenByListener).toBeUndefined()
    })

    it('does not answer a received message with one of its own', async () => {
      const tab = await signedInTab()
      const other = otherTab()

      act(() => {
        other.channel.postMessage({ type: 'signed-out' })
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(FakeBroadcastChannel.posted).toEqual([{ type: 'signed-out' }])
      expect(other.received).toEqual([])
    })

    it('does nothing harmful when a tab that is already signed out hears signed-out', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())
      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.status).toBe('unauthenticated'))
      vi.mocked(api.getCurrentUser).mockClear()

      act(() => {
        otherTab().channel.postMessage({ type: 'signed-out' })
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(tab.result.current.auth.user).toBeNull()
      expect(api.getCurrentUser).not.toHaveBeenCalled()
      expect(FakeBroadcastChannel.posted).toEqual([{ type: 'signed-out' }])
    })

    it('re-reads the session when another tab signs in, and posts nothing back', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())
      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.status).toBe('unauthenticated'))
      vi.mocked(api.getCurrentUser).mockClear()
      vi.mocked(api.getCurrentUser).mockResolvedValue(createUser({ id: '2' }))

      await act(async () => {
        otherTab().channel.postMessage({ type: 'signed-in' })
      })

      await waitFor(() => expect(tab.result.current.auth.user?.id).toBe('2'))
      expect(api.getCurrentUser).toHaveBeenCalledExactlyOnceWith(true)
      expect(tab.result.current.auth.isAuthenticated).toBe(true)
      expect(FakeBroadcastChannel.posted).toEqual([{ type: 'signed-in' }])
    })

    it('does not broadcast a sign-out when the probe it ran for another tab is refused', async () => {
      const tab = await signedInTab()
      const other = otherTab()
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())

      await act(async () => {
        other.channel.postMessage({ type: 'signed-in' })
      })

      await waitFor(() => expect(tab.result.current.auth.status).toBe('unauthenticated'))
      expect(FakeBroadcastChannel.posted).toEqual([{ type: 'signed-in' }])
      expect(other.received).toEqual([])
    })

    it('follows a sign-in in a second tab through the real login of that tab', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())
      const first = mountTab()
      const second = mountTab()
      await waitFor(() => {
        expect(first.result.current.auth.status).toBe('unauthenticated')
        expect(second.result.current.auth.status).toBe('unauthenticated')
      })
      vi.mocked(api.login).mockResolvedValue({ access_token: 't', token_type: 'bearer' })
      vi.mocked(api.getCurrentUser).mockResolvedValue(createUser({ id: '1' }))

      await act(async () => {
        await first.result.current.auth.login('a@example.com', 'pw')
      })

      await waitFor(() => expect(second.result.current.auth.isAuthenticated).toBe(true))
      expect(api.login).toHaveBeenCalledTimes(1)
    })

    it.each([
      ['an unknown type', { type: 'logout', user: 'someone' }],
      ['no type', { user: 'someone' }],
      ['null', null],
      ['a bare string', 'signed-out'],
    ])('ignores a message with %s and still acts on a known one after it', async (_label, payload) => {
      const tab = await signedInTab()
      const other = otherTab()
      vi.mocked(api.getCurrentUser).mockClear()

      act(() => {
        other.channel.postMessage(payload)
      })

      // A handler that read any message as "something changed" would re-read the session.
      expect(api.getCurrentUser).not.toHaveBeenCalled()
      expect(tab.result.current.auth.isAuthenticated).toBe(true)

      act(() => {
        other.channel.postMessage({ type: 'signed-out' })
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
    })
  })

  describe('losing the session without a logout', () => {
    it('clears the query cache when the session expires in a tab that held a user', async () => {
      const tab = await signedInTab()
      tab.queryClient.setQueryData(['projects'], [{ id: 'p1' }])
      const onSessionExpired = vi.mocked(api.setOnSessionExpired).mock.lastCall![0]

      act(() => {
        onSessionExpired?.()
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(tab.queryClient.getQueryData(['projects'])).toBeUndefined()
    })

    it.each([
      ['401', () => new UnauthorizedError()],
      ['403', () => new ForbiddenError('nope')],
    ])('clears the query cache when a probe is refused with %s in a tab that held a user', async (_label, makeError) => {
      const tab = await signedInTab()
      tab.queryClient.setQueryData(['projects'], [{ id: 'p1' }])
      vi.mocked(api.getCurrentUser).mockRejectedValueOnce(makeError())

      await act(async () => {
        await tab.result.current.auth.refreshUser()
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(tab.queryClient.getQueryData(['projects'])).toBeUndefined()
    })
  })

  describe('overlapping probes', () => {
    it('keeps a tab signed in when its anonymous mount probe is refused after a signed-in probe succeeded', async () => {
      const mountProbe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(mountProbe.promise)
      const tab = mountTab()
      const other = otherTab()
      vi.mocked(api.getCurrentUser).mockResolvedValueOnce(createUser({ id: '1' }))

      await act(async () => {
        other.channel.postMessage({ type: 'signed-in' })
      })
      await waitFor(() => expect(tab.result.current.auth.isAuthenticated).toBe(true))
      await act(async () => {
        mountProbe.reject(new UnauthorizedError())
      })

      expect(tab.result.current.auth.isAuthenticated).toBe(true)
      expect(tab.result.current.auth.user?.id).toBe('1')
      expect(FakeBroadcastChannel.posted).toEqual([{ type: 'signed-in' }])
      expect(other.received).toEqual([])
    })

    it('keeps a tab signed in when its mount probe is refused after its own login', async () => {
      const mountProbe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(mountProbe.promise)
      const tab = mountTab()
      const other = otherTab()
      vi.mocked(api.login).mockResolvedValue({ access_token: 't', token_type: 'bearer' })
      vi.mocked(api.getCurrentUser).mockResolvedValueOnce(createUser({ id: '1' }))

      await act(async () => {
        await tab.result.current.auth.login('a@example.com', 'pw')
      })
      await act(async () => {
        mountProbe.reject(new UnauthorizedError())
      })

      expect(tab.result.current.auth.isAuthenticated).toBe(true)
      expect(other.received).toEqual([{ type: 'signed-in' }])
    })

    it('stays signed out when a signed-in probe settles after a signed-out message', async () => {
      const tab = await signedInTab()
      const other = otherTab()
      const probe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(probe.promise)

      act(() => {
        other.channel.postMessage({ type: 'signed-in' })
      })
      act(() => {
        other.channel.postMessage({ type: 'signed-out' })
      })
      await act(async () => {
        probe.resolve(createUser({ id: '1' }))
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(tab.result.current.auth.user).toBeNull()
    })

    it.each([
      ['unauthenticated', () => Promise.reject(new UnauthorizedError()), false],
      ['authenticated', () => Promise.resolve(createUser({ id: '1' })), true],
    ])('settles to %s, not loading, when a login is refused while a mount probe is in flight', async (status, answer, isAuthenticated) => {
      const mountProbe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(mountProbe.promise)
      const tab = mountTab()
      const other = otherTab()
      vi.mocked(api.getCurrentUser).mockImplementationOnce(answer)
      vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

      await act(async () => {
        await tab.result.current.auth.login('a@example.com', 'wrong').catch(() => undefined)
      })
      await act(async () => {
        mountProbe.reject(new UnauthorizedError())
      })

      expect(tab.result.current.auth.status).toBe(status)
      expect(tab.result.current.auth.isAuthenticated).toBe(isAuthenticated)
      expect(api.getCurrentUser).toHaveBeenCalledTimes(2)
      expect(other.received).toEqual([])
    })

    it('makes no extra request when a login is refused and no probe is in flight', async () => {
      vi.mocked(api.getCurrentUser).mockRejectedValue(new UnauthorizedError())
      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.status).toBe('unauthenticated'))
      vi.mocked(api.getCurrentUser).mockClear()
      vi.mocked(api.login).mockRejectedValueOnce(new Error('Invalid credentials'))

      await act(async () => {
        await expect(tab.result.current.auth.login('a@example.com', 'wrong')).rejects.toThrow(
          'Invalid credentials'
        )
      })

      expect(api.getCurrentUser).not.toHaveBeenCalled()
      expect(tab.result.current.auth.status).toBe('unauthenticated')
    })

    it('stays signed out when a probe settles after a logout completed', async () => {
      const tab = await signedInTab()
      const probe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(probe.promise)

      act(() => {
        void tab.result.current.auth.refreshUser()
      })
      await act(async () => {
        await tab.result.current.auth.logout()
      })
      await act(async () => {
        probe.resolve(createUser({ id: '1' }))
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(tab.result.current.auth.user).toBeNull()
    })

    it('keeps a profile update that was made while a probe was in flight', async () => {
      const tab = await signedInTab()
      const probe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(probe.promise)

      act(() => {
        void tab.result.current.auth.refreshUser()
      })
      act(() => {
        tab.result.current.auth.setCurrentUser(createUser({ id: '1', first_name: 'Renamed' }))
      })
      await act(async () => {
        probe.resolve(createUser({ id: '1', first_name: 'Old' }))
      })

      expect(tab.result.current.auth.user?.first_name).toBe('Renamed')
    })

    it('ignores a probe refused while the login request is out, then ends up signed in', async () => {
      const mountProbe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(mountProbe.promise)
      const tab = mountTab()
      const other = otherTab()
      const listener = vi.fn()
      unsubscribers.push(registerSignOutListener(listener))
      const loginRequest = deferred<Awaited<ReturnType<typeof api.login>>>()
      vi.mocked(api.login).mockReturnValueOnce(loginRequest.promise)
      vi.mocked(api.getCurrentUser).mockResolvedValueOnce(createUser({ id: '1' }))

      let login!: Promise<void>
      act(() => {
        login = tab.result.current.auth.login('a@example.com', 'pw')
      })
      await act(async () => {
        mountProbe.reject(new UnauthorizedError())
      })
      expect(listener).not.toHaveBeenCalled()
      await act(async () => {
        loginRequest.resolve({ access_token: 't', token_type: 'bearer' })
        await login
      })

      expect(tab.result.current.auth.isAuthenticated).toBe(true)
      expect(other.received).toEqual([{ type: 'signed-in' }])
    })

    it('stays signed out when a probe settles after the session expired', async () => {
      const tab = await signedInTab()
      const probe = deferred<User>()
      vi.mocked(api.getCurrentUser).mockReturnValueOnce(probe.promise)
      const onSessionExpired = vi.mocked(api.setOnSessionExpired).mock.lastCall![0]

      act(() => {
        void tab.result.current.auth.refreshUser()
      })
      act(() => {
        onSessionExpired?.()
      })
      await act(async () => {
        probe.resolve(createUser({ id: '1' }))
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(tab.result.current.auth.user).toBeNull()
    })
  })

  describe('a different user signing in elsewhere', () => {
    it('clears the query cache before showing the new user', async () => {
      const tab = await signedInTab()
      tab.queryClient.setQueryData(['projects'], [{ id: 'p1' }])
      vi.mocked(api.getCurrentUser).mockResolvedValue(createUser({ id: '2' }))

      await act(async () => {
        otherTab().channel.postMessage({ type: 'signed-in' })
      })

      await waitFor(() => expect(tab.result.current.auth.user?.id).toBe('2'))
      expect(tab.queryClient.getQueryData(['projects'])).toBeUndefined()
    })

    it('keeps the query cache when the same user signed in again', async () => {
      const tab = await signedInTab()
      tab.queryClient.setQueryData(['projects'], [{ id: 'p1' }])
      vi.mocked(api.getCurrentUser).mockClear()

      await act(async () => {
        otherTab().channel.postMessage({ type: 'signed-in' })
      })

      await waitFor(() => expect(api.getCurrentUser).toHaveBeenCalledTimes(1))
      await waitFor(() => expect(tab.result.current.auth.isAuthenticated).toBe(true))
      expect(tab.result.current.auth.user?.id).toBe('1')
      expect(tab.queryClient.getQueryData(['projects'])).toEqual([{ id: 'p1' }])
    })
  })

  describe('where the channel cannot be opened', () => {
    async function signInAndOut() {
      vi.mocked(api.login).mockResolvedValue({ access_token: 't', token_type: 'bearer' })
      vi.mocked(api.getCurrentUser).mockResolvedValue(createUser({ id: '1' }))
      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.isAuthenticated).toBe(true))

      await act(async () => {
        await tab.result.current.auth.login('a@example.com', 'pw')
      })
      expect(tab.result.current.auth.isAuthenticated).toBe(true)
      expect(api.login).toHaveBeenCalledTimes(1)

      await act(async () => {
        await tab.result.current.auth.logout()
      })
      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(api.logout).toHaveBeenCalledTimes(1)
    }

    it('signs in and out as it did before when BroadcastChannel is not defined', async () => {
      vi.stubGlobal('BroadcastChannel', undefined)
      expect(typeof BroadcastChannel).toBe('undefined')

      await signInAndOut()

      expect(FakeBroadcastChannel.openCount(CHANNEL)).toBe(0)
    })

    it('signs in and out as it did before when the constructor throws', async () => {
      const constructor = vi.fn(function () {
        throw new Error('SecurityError')
      })
      vi.stubGlobal('BroadcastChannel', constructor)

      await signInAndOut()

      expect(constructor).toHaveBeenCalledWith(CHANNEL)
    })
  })
})
