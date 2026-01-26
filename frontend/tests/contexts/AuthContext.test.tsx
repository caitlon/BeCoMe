import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { api } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  api: {
    getToken: vi.fn(),
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  },
}))

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('throws error when useAuth is used outside AuthProvider', () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      'useAuth must be used within an AuthProvider'
    )
  })

  it('sets isAuthenticated to true when user exists', async () => {
    const mockUser = { id: '1', email: 'test@example.com', first_name: 'Test' }
    vi.mocked(api.getToken).mockReturnValue('valid-token')
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toEqual(mockUser)
  })

  it('sets isAuthenticated to false when no token', async () => {
    vi.mocked(api.getToken).mockReturnValue(null)

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })

  it('login calls api.login and refreshes user', async () => {
    const mockUser = { id: '1', email: 'test@example.com', first_name: 'Test' }
    vi.mocked(api.getToken).mockReturnValue(null)
    vi.mocked(api.login).mockResolvedValue({ access_token: 'new-token' })
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
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
    const mockUser = { id: '1', email: 'test@example.com', first_name: 'Test' }
    vi.mocked(api.getToken).mockReturnValue('valid-token')
    vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    act(() => {
      result.current.logout()
    })

    expect(api.logout).toHaveBeenCalled()
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })
})
