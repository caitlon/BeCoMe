// An in-memory BroadcastChannel for tests: every instance with the same name is one "tab" on a
// shared bus. Like the real one, a message goes to every other open instance of the name and
// never back to the sender, but delivery here is synchronous, so a test needs no timers.

type Handler = ((event: MessageEvent) => void) | null;

export class FakeBroadcastChannel {
  private static readonly open = new Map<string, Set<FakeBroadcastChannel>>();
  /** Every message ever posted, in order, whoever posted it. */
  static readonly posted: unknown[] = [];

  static reset(): void {
    FakeBroadcastChannel.open.clear();
    FakeBroadcastChannel.posted.length = 0;
  }

  /** The instances of a name that are still open. */
  static openCount(name: string): number {
    return FakeBroadcastChannel.open.get(name)?.size ?? 0;
  }

  /** The first instance of a name that is still open, which in a test is the code under test. */
  static firstOpen(name: string): FakeBroadcastChannel | undefined {
    return FakeBroadcastChannel.open.get(name)?.values().next().value;
  }

  onmessage: Handler = null;
  closed = false;

  constructor(readonly name: string) {
    const peers = FakeBroadcastChannel.open.get(name) ?? new Set<FakeBroadcastChannel>();
    peers.add(this);
    FakeBroadcastChannel.open.set(name, peers);
  }

  postMessage(data: unknown): void {
    if (this.closed) {
      throw new Error('FakeBroadcastChannel: channel is closed');
    }
    FakeBroadcastChannel.posted.push(data);
    FakeBroadcastChannel.open.get(this.name)?.forEach((peer) => {
      if (peer !== this) {
        peer.onmessage?.({ data } as MessageEvent);
      }
    });
  }

  close(): void {
    this.closed = true;
    FakeBroadcastChannel.open.get(this.name)?.delete(this);
  }
}
