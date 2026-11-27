/**
 * Tells the other tabs of this browser that the session changed, so a sign-out in
 * one tab signs every tab out at once instead of at its own next request.
 *
 * A message carries its type and nothing else: no user id, email, token or any other
 * data. A tab that receives one re-reads the session or drops it locally, and learns
 * nothing about who the user was. BroadcastChannel is same-origin and never delivers a
 * message to the instance that posted it. Where it is not defined (an old browser,
 * server rendering), opening the channel returns one that does nothing, which is how
 * the app behaved before this existed.
 */

const CHANNEL_NAME = 'become-auth';

export type AuthBroadcastType = 'signed-out' | 'signed-in';

export interface AuthBroadcast {
  readonly post: (type: AuthBroadcastType) => void;
  readonly close: () => void;
}

const NOOP: AuthBroadcast = { post: () => undefined, close: () => undefined };

function isAuthBroadcastType(value: unknown): value is AuthBroadcastType {
  return value === 'signed-out' || value === 'signed-in';
}

/**
 * Opens the channel and calls `onMessage` for every message another tab posts. Anything
 * that is not one of the two known types is ignored. Close the result when the owner unmounts.
 */
export function openAuthBroadcast(onMessage: (type: AuthBroadcastType) => void): AuthBroadcast {
  if (typeof BroadcastChannel === 'undefined') {
    return NOOP;
  }
  let channel: BroadcastChannel;
  try {
    channel = new BroadcastChannel(CHANNEL_NAME);
  } catch {
    return NOOP;
  }
  channel.onmessage = (event: MessageEvent<unknown>) => {
    const data = event.data as { type?: unknown } | null;
    if (data !== null && typeof data === 'object' && isAuthBroadcastType(data.type)) {
      onMessage(data.type);
    }
  };
  return {
    post: (type) => {
      try {
        channel.postMessage({ type });
      } catch {
        // A closed channel leaves this tab's own sign-out intact.
      }
    },
    close: () => {
      channel.onmessage = null;
      channel.close();
    },
  };
}
