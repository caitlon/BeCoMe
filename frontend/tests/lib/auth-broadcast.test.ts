import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { openAuthBroadcast } from '@/lib/auth-broadcast'
import { FakeBroadcastChannel } from '@tests/support/fake-broadcast-channel'

const NAME = 'become-auth'

describe('openAuthBroadcast', () => {
  beforeEach(() => {
    FakeBroadcastChannel.reset()
    vi.stubGlobal('BroadcastChannel', FakeBroadcastChannel)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('delivers the type another tab posts, and never its own message back', () => {
    const received = vi.fn()
    const own = vi.fn()
    const mine = openAuthBroadcast(own)
    openAuthBroadcast(received).post('signed-out')

    expect(own).toHaveBeenCalledExactlyOnceWith('signed-out')
    expect(received).not.toHaveBeenCalled()
    mine.close()
  })

  it('posts a message that holds the type and nothing else', () => {
    const channel = openAuthBroadcast(() => undefined)
    channel.post('signed-in')
    channel.post('signed-out')

    expect(FakeBroadcastChannel.posted).toEqual([{ type: 'signed-in' }, { type: 'signed-out' }])
    channel.close()
  })

  it('ignores a message that is not one of the two types', () => {
    const onMessage = vi.fn()
    const channel = openAuthBroadcast(onMessage)
    const stranger = new FakeBroadcastChannel(NAME)
    for (const data of [null, 'signed-out', 42, {}, { type: 'logout' }, { type: 1 }]) {
      stranger.postMessage(data)
    }

    expect(onMessage).not.toHaveBeenCalled()
    channel.close()
  })

  it('stops delivering and frees the channel once closed', () => {
    const onMessage = vi.fn()
    const channel = openAuthBroadcast(onMessage)
    expect(FakeBroadcastChannel.openCount(NAME)).toBe(1)

    channel.close()
    expect(FakeBroadcastChannel.openCount(NAME)).toBe(0)
    new FakeBroadcastChannel(NAME).postMessage({ type: 'signed-out' })

    expect(onMessage).not.toHaveBeenCalled()
  })

  it('does nothing, and does not throw, where BroadcastChannel is not defined', () => {
    vi.stubGlobal('BroadcastChannel', undefined)
    const channel = openAuthBroadcast(vi.fn())

    expect(() => {
      channel.post('signed-out')
      channel.close()
    }).not.toThrow()
  })

  it('does nothing when the browser refuses to open the channel', () => {
    vi.stubGlobal(
      'BroadcastChannel',
      class {
        constructor() {
          throw new Error('SecurityError')
        }
      }
    )
    const channel = openAuthBroadcast(vi.fn())

    expect(() => channel.post('signed-in')).not.toThrow()
  })

  it('keeps the tab working when a post fails', () => {
    const channel = openAuthBroadcast(vi.fn())
    FakeBroadcastChannel.firstOpen(NAME)!.close()

    expect(() => channel.post('signed-out')).not.toThrow()
  })
})
