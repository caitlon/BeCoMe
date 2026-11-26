/**
 * Keeps frontend unit tests off the network.
 *
 * `installNetworkGuard()` replaces `fetch`, `XMLHttpRequest`, `WebSocket` and
 * `navigator.sendBeacon` with versions that refuse to send anything. A refusal fails the call
 * with a message naming the URL, and is also recorded, because application code often catches
 * a rejected request and carries on: `failOnBlockedRequests()` then fails the test that made it.
 *
 * `tests/setup.ts` installs the guard once per file and again after every test, so a test that
 * assigned `globalThis.fetch` directly does not leave its mock behind. A test mocks a request
 * with `vi.stubGlobal('fetch', ...)`, which replaces the guard until `vi.unstubAllGlobals()`.
 * A test that triggers the guard on purpose calls `takeBlockedRequests()` to clear the record.
 */

interface BlockedRequest {
  /** The API the request went through: `fetch`, `XMLHttpRequest`, `WebSocket` and so on. */
  api: string;
  url: string;
}

const blocked: BlockedRequest[] = [];

const HOW_TO_MOCK =
  "Frontend unit tests send no network requests: mock it, for example " +
  "vi.stubGlobal('fetch', vi.fn(...)), likewise for XMLHttpRequest and WebSocket, " +
  "or vi.spyOn(navigator, 'sendBeacon') for sendBeacon.";

function urlOf(input: unknown): string {
  if (input === undefined) return "";
  if (typeof input === "object" && input !== null && "url" in input) {
    return String(input.url);
  }
  return String(input);
}

function refuse(api: string, url: string): Error {
  blocked.push({ api, url });
  return new Error(`Unmocked network request: ${api} ${url || "(no URL)"}. ${HOW_TO_MOCK}`);
}

function guardedFetch(input: RequestInfo | URL): Promise<Response> {
  return Promise.reject(refuse("fetch", urlOf(input)));
}

// Subclasses the environment's own class so a test can still open a request, set headers and
// read the state constants. Only the call that sends is refused. Undefined where the environment
// has no XMLHttpRequest, such as the node environment.
const BaseXhr = typeof XMLHttpRequest === "undefined" ? undefined : XMLHttpRequest;
const GuardedXhr =
  BaseXhr &&
  class GuardedXMLHttpRequest extends BaseXhr {
    #url = "";

    override open(
      method: string,
      url: string | URL,
      isAsync = true,
      username?: string | null,
      password?: string | null
    ): void {
      this.#url = urlOf(url);
      super.open(method, url, isAsync, username, password);
    }

    override send(): void {
      throw refuse("XMLHttpRequest", this.#url);
    }
  };

// Undefined where the environment has no WebSocket. Keeps the state constants, which code
// compares readyState against.
const GuardedWebSocket =
  typeof WebSocket === "undefined"
    ? undefined
    : class GuardedWebSocket {
        static readonly CONNECTING = 0;
        static readonly OPEN = 1;
        static readonly CLOSING = 2;
        static readonly CLOSED = 3;

        constructor(url?: string | URL) {
          throw refuse("WebSocket", urlOf(url));
        }
      };

// Whether the environment has a sendBeacon, read once so that a test which removes or stubs it
// does not leave later tests unguarded.
const hasSendBeacon = typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function";

function guardedSendBeacon(url: string | URL): boolean {
  throw refuse("navigator.sendBeacon", urlOf(url));
}

function define(target: object, key: string, value: unknown): void {
  Object.defineProperty(target, key, {
    value,
    writable: true,
    configurable: true,
    enumerable: true,
  });
}

/**
 * Puts the guard over every request API the environment has, replacing whatever stands there.
 * Under vitest's happy-dom `window` is `globalThis`, so defining on `globalThis` covers both.
 */
export function installNetworkGuard(): void {
  define(globalThis, "fetch", guardedFetch);
  if (GuardedXhr) define(globalThis, "XMLHttpRequest", GuardedXhr);
  if (GuardedWebSocket) define(globalThis, "WebSocket", GuardedWebSocket);
  if (hasSendBeacon) define(navigator, "sendBeacon", guardedSendBeacon);
}

/** Returns the requests the guard refused since the last call and clears the record. */
export function takeBlockedRequests(): BlockedRequest[] {
  return blocked.splice(0);
}

/**
 * Throws when the guard refused a request since the last call, whatever the code under test did
 * with the refusal, and clears the record.
 */
export function failOnBlockedRequests(): void {
  const requests = takeBlockedRequests();
  if (requests.length === 0) return;
  const lines = requests.map(({ api, url }) => `  ${api} ${url || "(no URL)"}`).join("\n");
  throw new Error(
    `The test tried to send ${requests.length} network request(s), whatever the code did with ` +
      `the refusal:\n${lines}\n${HOW_TO_MOCK}`
  );
}
