import { ReactNode } from 'react'
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import { AuthProvider, useAuth, registerSignOutListener } from '@/contexts/AuthContext'
import { useToast } from '@/hooks/use-toast'
import { api } from '@/lib/api'
import { ForbiddenError, UnauthorizedError } from '@/lib/errors'
import i18n from '@/i18n'
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

    it('ignores a message that is not one of the two types', async () => {
      const tab = await signedInTab()

      act(() => {
        otherTab().channel.postMessage({ type: 'logout', user: 'someone' })
      })

      expect(tab.result.current.auth.isAuthenticated).toBe(true)
    })
  })

  describe('where BroadcastChannel is not defined', () => {
    it('signs in and out as it did before, without a channel', async () => {
      vi.stubGlobal('BroadcastChannel', undefined)
      vi.mocked(api.login).mockResolvedValue({ access_token: 't', token_type: 'bearer' })
      vi.mocked(api.getCurrentUser).mockResolvedValueOnce(createUser({ id: '1' }))
      const tab = mountTab()
      await waitFor(() => expect(tab.result.current.auth.isAuthenticated).toBe(true))

      await act(async () => {
        await tab.result.current.auth.login('a@example.com', 'pw')
        await tab.result.current.auth.logout()
      })

      expect(tab.result.current.auth.status).toBe('unauthenticated')
      expect(FakeBroadcastChannel.posted).toEqual([])
      tab.unmount()
    })
  })
})
