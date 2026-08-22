# Security

What is actually implemented in BeCoMe to keep the product and its users' data safe, and
how to operate the pieces that need runbooks. This is a description of the running system,
not a wishlist. Deployment topology lives in [`environments.md`](environments.md); the
academic threat model (attack trees, residual-risk argument) lives in the thesis
workspace and is not duplicated here.

## Status at a glance

| Area | Status | Where |
|------|--------|-------|
| Authentication -- JWT, refresh rotation, lockout | Implemented | `api/auth/` |
| Session transport -- HttpOnly cookies + CSRF | Implemented | `api/auth/cookies.py`, `api/middleware/csrf.py` |
| Authorization and tenant isolation | Implemented | `api/dependencies.py` |
| Rate limiting and abuse control | Implemented | `api/middleware/rate_limit.py` |
| Input validation | Implemented | `api/schemas/` |
| Configuration invariants per profile | Implemented | `api/config.py` |
| Network and edge -- Cloudflare, CORS, headers | Implemented | `api/main.py`, Cloudflare |
| Logging, observability, and PII scrubbing | Implemented | `api/logging_config.py`, `api/logging_context.py` |
| Secrets management and rotation | Implemented | Railway variables, [below](#secrets) |
| GDPR export and erasure | Implemented | `api/routes/users.py` |
| Database least-privilege, network, auditing | Implemented | `scripts/db/`, `api/db/engine.py` |
| Automated database backups | Partial -- manual dumps | `scripts/db/backup.sh` |

## Authentication

Sessions are stateless JWTs signed with `SECRET_KEY` (HS256). Login returns a short-lived
access token and a longer-lived refresh token. Refresh tokens rotate: each refresh mints a
fresh pair tied to a rotation family (a `sid` claim). Presenting a refresh token that has
already been rotated is treated as theft and revokes the entire family, so a stolen token
stops working the moment the legitimate client refreshes. Changing the password stamps a
per-user cutoff that rejects every token issued before it. Both the change and the reset
route record that cutoff *before* they write the new password, so a revocation-store fault
aborts the operation instead of leaving a fresh password with every old session still
alive. The cutoff itself expires
once the longest-lived token would have, so it is not stored forever.

Passwords are hashed with bcrypt. Because bcrypt silently truncates input at 72 bytes, the
password is SHA-256 pre-hashed and base64-encoded first (`api/auth/password.py`), which is
the approach bcrypt's own maintainers recommend. A strength policy is enforced on
registration and password change.

Two abuse paths on the login endpoint are closed. Repeated failures lock the account for a
cooldown window (`api/auth/login_throttle.py`), which stops online brute force and
credential stuffing against a single account. And an unknown email still runs a dummy hash
so a wrong-email response takes the same time as a wrong-password one -- login timing
cannot be used to enumerate which addresses have accounts.

## Registration and email verification

An account is created unverified and cannot log in until the address is confirmed. Login
checks `email_verified_at` only *after* the password verifies, and answers `403`; checking
first would answer differently for an address that has an account and one that does not,
which is the enumeration oracle the uniform `401` exists to prevent.

`POST /auth/register` always answers `202` with one fixed body. Behind it,
`RegistrationService` picks one of three branches: a free address creates an unverified
account, a taken-but-unverified address writes nothing at all, and a taken-and-verified
address is left untouched while its owner is emailed a notice that someone tried to sign up
with it.

**A submission is bound to the link it mints, never to the account.** The activation token
carries the submitted password hash and names (`email_verification_tokens`, all three
columns `NOT NULL`), and they are written to the account only when that specific token is
redeemed. The alternative -- storing the newest submission on the account row -- is an
unauthenticated account-takeover primitive: whoever submits last would decide what every
outstanding link opens, so an attacker submits `victim@example.com` after the real owner
signed up, the owner clicks the link they already have, and the account activates on the
attacker's password.

**Redemption also requires the password the token carries.** `POST /auth/verify-email` takes
`{token, password}` and checks the password against the token's `hashed_password`, never
against the `users` row. That is what closes the class the binding above only narrows.
Anyone can cause an activation link to arrive at an address they do not control -- a repeat
registration puts a fresh one at the top of the victim's inbox, and nothing distinguishes it
from their own. With the password required, the stranger's link is dead in both hands: the
recipient does not know the submitted password, and the submitter never sees the link. The
victim's own link, with the victim's own password, still works. Neither party can activate
the other's submission.

Three consequences follow. Issuing a link does **not** retire the outstanding ones, unlike
password reset -- several live links for one unconfirmed address is the correct state, since
each is single-use and carries its own submission, and retiring them is exactly how one
submitter would kill another's pending link. Redemption is refused once the address is
verified, with the same opaque `400` an unknown token gets: a token minted while the account
was unconfirmed carries a password, so redeeming it afterwards would rewrite the credentials
of an account somebody is already using -- and refusing before the password is weighed also
keeps the endpoint from being able to lock a live account out of its own login. And a
completed password reset sets `email_verified_at` too, which retires every outstanding
activation link in one move; a reset link proves control of the address exactly as an
activation link does, so reclaiming an address somebody pre-registered is one step for the
credentials. It is not one step for the display name -- see "Accepted risks" below.

That makes an activation and a reset the two operations that can confirm the same account, so
both go through a `_claim_account` that writes `UPDATE ... WHERE email_verified_at IS NULL`
whenever the row it loaded was still pending, and lets the database pick the winner. The loser
writes nothing and gets the opaque `400`; on the reset side its token is deliberately left
unspent, so following the same link again succeeds against the now-confirmed account. A reset
whose account was already confirmed when its token resolved has nothing to race -- redemption
is refused once `email_verified_at` is set -- so it writes by id alone. Reading the row and
writing it back would instead let a reset that started while the account was still pending
overwrite the password an activation had just applied, seconds after telling whoever redeemed
it to sign in; bcrypt alone holds that window open for a few hundred milliseconds.

A wrong password answers `403` with its own wording, not the opaque `400` the token errors
share. Whoever reaches that point already holds a live link, so admitting the link is fine
tells them nothing new -- while telling a user who mistyped that their link is broken would
send them round the loop asking for another one that would fail the same way. The guessing
oracle that opens is capped by its own per-token lockout (`api/auth/login_throttle.py`),
namespaced apart from the one `/login` uses: this endpoint's lockout can only be tripped by
someone who already holds a live token, so a run of failed logins -- which anyone who merely
knows the address can produce -- can never deny someone their own activation.

**The lockout keys on the token's hash, not the account.** Issuing a link never retires an
earlier one (see above), so one unconfirmed address can carry several live tokens at the same
time. A single bucket shared by all of them would reopen, one level down, the same shape of
denial the login/activation split above already prevents: anyone who merely obtains a single
token -- forwarded by its recipient, or intercepted, rather than read from the mailbox itself
-- could spend the account's entire activation budget against it and, because every failure
refreshes the window, keep it spent indefinitely, locking the real owner out of a different,
freshly resent link they hold instead. Keying on the token confines that damage to the token
it was spent against. It does not widen what one token can be guessed: any single token still
allows at most ten activation failures against its own password, the same bound described
below. Nor does it hand an attacker more guesses to spend -- `resend-verification` only ever
mints a token carrying the password its own caller submitted, and the mail carrying it goes to
the account's address, not back to whoever asked, so minting more tokens never buys a guess
against a password the caller does not already know.

**The two budgets are independent, and they add up.** Each endpoint allows 10 failures per 15
minutes and consults only its own counter -- login's keyed per account, activation's per token
-- so nine failed logins followed by ten activation guesses against one token is nineteen wrong
passwords reachable against that token's password inside a window. A shared counter is the only
thing that would bound the total, and a shared counter is exactly what the split exists to
prevent. Moving the login counter takes no credential and every failure refreshes its expiry,
so any endpoint that reads it can be held shut indefinitely by a stranger who knows nothing but
the address. The activation counter cannot be moved without a live single-use token, and that
token exists in one place: the mailbox it was sent to. Whoever reaches the extra ten guesses has
therefore already read the mail, and reading the mail takes the account outright through
`forgot-password` without guessing at anything. The extra guesses hand an attacker a weaker
capability than the one they used to get them. A mismatch does still spend from the login
counter, which costs the guesser instead of bounding them: ten activation mismatches lock
`/login` too, so the total only grows when the login guesses come first.
`POST /auth/reset-password` clears the login lockout on success, so an attacker's failed
guesses cannot keep an account locked out of login after its owner has proven control of
the address and set a new password.

The notice mail carries a static `/forgot-password` link, never a minted reset token -- an
unauthenticated registration attempt must not be able to mail anyone a working reset link.

Two side channels are closed alongside the response body. Every branch runs bcrypt on the
submitted password, including the one that writes nothing, so none can be identified by
answering hundreds of milliseconds faster. And the emails the flow can trigger share one
per-address budget (`api/auth/email_throttle.py`, keyed by a hash of the address), so
submitting a victim's address in a loop from rotating IPs cannot flood their inbox past the
per-IP limiter. Suppression never changes the response.

Every send spends from that budget, including the one on the branch that creates the account
-- which is the only branch never *denied* by it. The distinction matters in both directions.
Never denied, because that branch fires at most once per address (a second submission is by
definition no longer free), so charging it would let a stranger drain the allowance with five
unauthenticated `resend-verification` calls and pre-empt a signup that has not happened yet:
the victim would register, get the normal `202`, receive nothing, and be left with an account
that cannot log in. Still spending, because a send that left the budget clean would make two
back-to-back submissions separate a free address from a taken one -- the free one mailing on
both probes, the taken one going quiet after the first -- and the awaited round trip to the
mail provider is exactly the difference the uniform `202` exists to hide. A resend request
for an address with nothing to send spends nothing, for the same anti-denial reason as the
creating branch, and it mails nothing either, so it opens no timing difference.

Activation tokens otherwise follow the password-reset design: `secrets.token_urlsafe(32)`,
only the SHA-256 hash stored, single use, expiring after
`EMAIL_VERIFICATION_TOKEN_TTL_HOURS` (24 by default). Unknown, spent, and expired tokens all
get one opaque `400`. `POST /auth/resend-verification` takes `{email, password}` and answers
`202` identically for an unknown address, an unverified one, and an already-verified one.
Taking the password makes it a repeat registration minus the names: the link it mails carries
that password like any other, and the names come from the account, which is all a resend
request can know. An address-only resend would mint a link with nothing to prove, which
anyone receiving the mail could follow.

Before any of that touches the database, the submitted address goes through
`EmailAddressPolicy` (`api/services/email_policy.py`): a vendored disposable-domain
blocklist and an MX/A/AAAA reachability check that fails open. Only a definitive negative
rejects: NXDOMAIN, a confirmed absence of every record type, or an RFC 7505 null MX, which is
the domain itself declaring that it accepts no mail and which overrides the A/AAAA fallback
the way the RFC requires. Both verdicts depend only on the domain string, never on database
state, so their `400` leaks nothing about account existence. Each has a runtime kill switch
(`DISPOSABLE_EMAIL_BLOCKING_ENABLED`, `MX_CHECK_ENABLED`) in case either starts rejecting
real users.

## Session transport (cookies and CSRF)

The browser client keeps no token in JavaScript-readable storage. Login and refresh set the
access and refresh tokens as cookies marked `HttpOnly`, `SameSite=Strict`, and `Secure`
(the `Secure` flag follows the request scheme, so it is on in production behind TLS and off
for the plain-HTTP dev and e2e stacks; see `api/auth/cookies.py`). An XSS payload therefore
cannot read the session the way it could read `localStorage`.

`SameSite=Strict` already stops the session cookies from riding along on cross-site
requests. On top of that, a CSRF check (`api/middleware/csrf.py`) defends the same-site
case, and the case `SameSite` does not cover at all: "site" means the registrable domain,
so a page on any `becomify.app` subdomain is same-site with the API and its requests do
carry the session cookies.

The token is **derived from the session**, not drawn at random and stored beside it:
`csrf_token_for(sid)` is an HMAC of the session id under the application secret
(`api/auth/cookies.py`). On a mutating request the middleware reads the session cookie,
takes the `sid` from it, recomputes the expected token, and compares it against the
`X-CSRF-Token` header. That comparison is against a value the server derives, never
against something the client sent.

The difference matters against an attacker who can write cookies for the API host -- one
sitting on a sibling `becomify.app` subdomain, since a cookie set with
`Domain=becomify.app` shadows ours. A plain cookie-versus-header comparison loses to that
attacker twice: they can plant a value they know in the `csrf_token` cookie and echo it in
the header, and they can equally plant a token minted for a session they legitimately
hold. Binding the token to the victim's `sid` closes both, since forging one for a session
you do not hold means forging an HMAC.

Deriving it also means the check cannot be waived by omission. It keys on the *session*
cookie, so any request that authenticates as somebody is checked -- where the old
comparison armed itself on the presence of the CSRF cookie and silently passed anything
arriving without it. Bearer-token clients carry no session cookie and are unaffected, as
are the pre-session auth endpoints (`login`, `register`, `refresh`, password reset), so a
stale cookie left by a revoked session can never block a fresh login. Logout stays
CSRF-protected.

Reading the `sid` deliberately skips expiry, revocation, and the per-user cutoff
(`session_id_from_access_token`): the signature is verified, but the rest is the
authentication layer's job, and checking it here would put three Redis round trips in
front of every mutating request. A token failing any of them is refused moments later
anyway, with the CSRF check already applied.

The SPA gets the value from a response header rather than from the cookie. Login and
refresh send it in an `X-CSRF-Token` **response** header, and `GET /auth/me` -- the app's
session probe on mount -- reports the token for the session it authenticates as, so a page
reload recovers it (`api/auth/cookies.py::set_csrf_header`). The header is what makes this
workable on the deploys: the cookie carries no `Domain` attribute, so it belongs to the API
host, and the app is served from a different one, where `document.cookie` shows it nothing
while the browser keeps sending it. Reading the cookie still works when the two share an
origin, which is how local development runs behind the Vite proxy, and stays the fallback.
`CORSMiddleware` names the header in `expose_headers`; without that the browser withholds
it from cross-origin JavaScript.

Handing the value back changes nothing about the guarantee. It is meant to be readable by
the client that owns the session, and CORS answers against an explicit origin allow-list,
so a hostile origin can no more read the header than the cookie. Widening the cookie with
`Domain=becomify.app` would look like the smaller fix and is the one to avoid: dev,
staging, and production all sit under that parent and would overwrite each other's token,
breaking whichever was visited last. Deriving the token also retired a sharp edge on
`/auth/me`, which used to echo the caller's own cookie back: Starlette's RFC 2109 cookie
unescape turns `csrf_token="\012..."` into a real newline, and uvicorn writes response
headers without validating them, so that echo was a response-splitting primitive kept in
check by a filter. There is no client value on that path any more.

What this does **not** cover is an attacker on a sibling subdomain shadowing the *session*
cookie itself, which would log the victim into the attacker's account rather than forge a
request. `__Host-` cookie prefixes are the fix for that; they require the `Secure`
attribute, and WebKit refuses such cookies over plain `http://localhost`, so adopting them
means moving the whole e2e stack onto TLS first.

The `Authorization: Bearer` path is kept alongside the cookie path for programmatic clients
and the test suite; it authenticates the same tokens without the cookie or CSRF machinery.
Such a client sends no session cookie, so it gets no header back either.

## Authorization and tenant isolation

BeCoMe is multi-tenant: every project-scoped route runs through `RequireProjectAccess`
(`api/dependencies.py`) before it reads or writes anything. A caller who is not a member of
the project gets `404 Not Found` -- the same answer as a project that does not exist -- so
the API never confirms the existence of a project to someone with no business knowing about
it. A member who lacks the required role (an expert attempting an admin action) gets `403`,
since they already know the project is there. Denials are logged with the project and user
id for audit.

Row-level security is deliberately off (migration `c83186b79ad7`): the tables arrived from
Supabase with RLS enabled and forced but no policies, which is a no-op for a superuser and
a total lockout for the least-privilege `become_app` role. Authorization therefore has no
database backstop -- if a route does not check, nothing does -- so
`tests/unit/api/test_route_authorization.py` enforces it structurally instead of trusting
review. It walks the application's real route table and asserts two things: every route
taking a `project_id` has `RequireProjectAccess` somewhere in its dependency tree, and
every route taking *any* path parameter is either guarded the same way or listed in
`UNGUARDED_BY_DESIGN` with the check that stands in for the dependency.

The second guard exists because the first cannot see the routes that matter most here: an
identifier like `{invitation_id}` points at somebody else's record just as squarely as a
project id does, and carries no `project_id` for the first check to notice. Three routes
are exempt today -- the public avatar proxy, and accepting or declining an invitation,
where `InvitationService` compares `invitee_id` against the caller because there is no
membership to check until the invitation is accepted. A new route naming an object fails
the suite until somebody either wires in the dependency or records what replaces it.

## Rate limiting and abuse control

Rate limiting is handled by slowapi backed by Redis, with an in-memory fallback if Redis is
unreachable (`api/middleware/rate_limit.py`). Two global ceilings apply to every route --
`300/minute` and a `20/second` burst -- so no endpoint is unbounded even if it forgot its
own limit. On top of that, routes carry tighter limits by risk:

| Limit | Value | Applied to |
|-------|-------|-----------|
| Auth | `5/minute` | Login, register |
| Password reset | `3/minute` | Forgot / reset password, verify / resend verification |
| Write | `30/minute` | Mutations that also recalculate |
| Upload | `10/minute` | File uploads |
| Standard | `60/minute` | Everything else |

The limiter keys on the real client IP. Behind Cloudflare and Railway the app trusts the
forwarded protocol and client address only from the proxy hop it is configured for; a
`X-Forwarded-For` header from an untrusted source is ignored, so a client cannot spoof its
way around the per-IP limits. Auth rate limiting fails closed. Request bodies over the
configured ceiling are rejected with `413` before they are buffered, and profile-photo
uploads are streamed and size-capped rather than read whole into memory.

A photo upload passes three independent checks (`api/services/storage/validation.py`): the
declared content type must be one of four image types, the leading magic bytes must match
that declaration, and the pixel canvas must fit the avatar budget (4096x4096, no side over
8192). The last one exists because bytes and pixels are not the same limit: image formats
compress uniform areas so well that a 35 KB PNG can declare a 25-megapixel canvas, which
costs hundreds of megabytes the moment anything decodes it. Only the header is parsed, so
rejecting such a file is free.

## Input validation

Request DTOs are Pydantic models with `extra="forbid"` (`api/schemas/`), so an unexpected
field is a `422` rather than a silently ignored parameter. String fields carry length caps,
free-text names are HTML-sanitized, and list endpoints clamp their page size
(`MAX_PAGE_SIZE = 100`, `api/pagination.py`) so a single request cannot ask the database for
an unbounded result set. The GDPR export is the one deliberate exception to the list caps --
Article 20 requires the full dataset -- and that is documented at the call site.

## Configuration and profiles

The app runs under one of three profiles selected by `APP_ENV`: `dev`, `test`, `prod`
(`api/config.py`). Deployed services are held to invariants that fail startup rather than
boot insecurely (`_validate_deploy_invariants`): the `SECRET_KEY` must be strong, SQLite is
rejected in favor of PostgreSQL, `redis_url` must be set, `CORS_ORIGINS` may not be
localhost, a real email provider must be configured, `DEBUG` must be off, and
`MIGRATION_DATABASE_URL` must be set explicitly so migrations keep running as the
privileged role. Production additionally requires `cloudflare_origin_secret`.

"Deployed" is not the same as "not dev". The dev *service* has its own database and a
public URL, so it is held to the same invariants: anything running with a
`RAILWAY_ENVIRONMENT_NAME` counts, whatever its `APP_ENV`. A laptop and a CI runner carry
no such marker and stay unconstrained. The pytest runner is distinguished from a deployed
`test` (staging) environment by a `TESTING` flag, so the invariants guard staging without
breaking the local suite. Interactive API docs (`/docs`) are served only outside
production.

## Network and edge

The public origin is `becomify.app`, served through Cloudflare, and each deployed
environment has its own host under it: `api.becomify.app` (production),
`api-harbor.becomify.app` (staging), `api-atelier.becomify.app` (dev). A Cloudflare
Transform Rule per host injects a shared secret header the origin then requires
(`cloudflare_origin_secret`, a different value per environment, demanded of every deploy
by `Settings._validate_deploy_invariants`).

The lock decides what the origin *believes*, not what it *accepts*. Railway also gives each
service a `*.up.railway.app` address, and those answer, so the edge can still be bypassed;
what the secret buys is that a request arriving without it is keyed under a single constant
rather than off a forwarding header the origin cannot vouch for (`api/utils/client_ip.py`).
That matters because uvicorn runs with `--proxy-headers --forwarded-allow-ips='*'`, which
makes `request.client.host` only as trustworthy as whatever wrote `X-Forwarded-For`. It
also makes the rate-limit key correct rather than merely safe: without the lock, every
request that did transit Cloudflare is keyed under the *edge's* address, collapsing all
callers into one bucket. Closing the bypass itself -- so the WAF and bot rules cannot be
skipped -- means retiring the `*.up.railway.app` domains, which is still open. CORS is configured
with explicit allowed origins and `allow_credentials=True` (required for the cookie
session). It permits the `X-CSRF-Token` header on the way in and exposes it on the way
out, since the SPA reads the CSRF token off the response.

Both tiers send security response headers: the API from middleware
(`api/middleware/security_headers.py`), the SPA from nginx (`frontend/nginx.conf`). Their
Content-Security-Policies match except where the SPA genuinely needs more. Its
`connect-src` names the API origin, which is cross-origin on the deploys, plus the Sentry
ingest hosts the browser SDK reports to. Its `img-src` names that same API origin, because
profile photos are served by the API and rendered in `<img>` tags -- an image load, which
`connect-src` does not cover. That origin is baked into the policy when the image is built,
from the same `VITE_API_URL` build argument the bundle uses, so the served policy cannot
drift from the URL the app actually calls. Both directives are asserted against the config
in `tests/integration/test_frontend_csp.py`: a CSP that under-permits fails silently, since
the browser drops the request before it reaches the origin and nothing appears in the logs. `X-XSS-Protection` is set
to `0` on both tiers on purpose: the legacy auditor it enables is unreliable, browsers have
dropped it, and its blocking mode has itself leaked cross-origin information. The CSP is
what constrains injection.

The correlation ID is not taken on trust either. An inbound `X-Request-ID` is echoed on the
response and written to every log record of the request, so it is reused only when it looks
like an ID -- a short, conservative alphabet -- and replaced with a fresh UUID otherwise
(`api/middleware/request_logging.py`).

## Logging, observability, and privacy

Logs are structured JSON in the deployed profiles. Each request is tagged with an
`X-Request-ID`, and a context filter binds that request id and the acting user id onto every
`api.*` log record through contextvars (`api/logging_context.py`), so a service or security
log line can be traced back to a request without threading identifiers by hand. Personal
data is kept out of the logs: email addresses are recorded as a truncated keyed digest
(`email_hash`), not in the clear. The key matters -- a plain SHA-256 of an address is
reproducible by anyone holding the logs, so they could confirm whether a given person has
an account by hashing a guess. The tag is an HMAC keyed with `LOG_HASH_KEY` (falling back
to `SECRET_KEY`), which makes it meaningless outside the application while still
correlating repeated attempts on one account. Rotating the fallback re-tags every later
record, so set `LOG_HASH_KEY` explicitly where that correlation has to survive a rotation.

The rule for any new log record: identifiers, keyed tags, and counts, never the values
themselves. Allowed are `user_id`, `project_id`, `invitation_id`, `jti`, `sid`, `ip`,
`status_code`, `duration_ms`, `row_count`, and the `reason` a request was refused. Never
logged, at any level: passwords and password hashes, raw JWTs, the CSRF cookie or header
value, the email API key or bucket credentials, the `Authorization` header, any request or
response body, raw email addresses, activation or reset tokens and the URLs carrying them,
and free-text user content such as a project description.

Two specific traps are worth naming. First, `_digest()` in `api/auth/login_throttle.py` and
`api/auth/email_throttle.py` is a **plain, unkeyed** SHA-256 of the identifier -- it exists
to key the store, not to be logged. Writing it out would rebuild exactly the oracle
`hash_email` is keyed to prevent, so records in those modules name the flow (`key_prefix`,
`op`) and never the account; the address-scoped event belongs at the call site in
`api/routes/auth.py`, which has the keyed tag. Second, `sqlalchemy.engine` is pinned at
WARNING in `api/logging_config.py` and must stay below DEBUG on any deployed service: its
DEBUG level prints bound query parameters, which on this schema means bcrypt hashes,
addresses, names, and reset-token hashes shipped to the log drain in the clear. That pin
matters because the dev deploy now runs at `LOG_LEVEL=DEBUG` against a real database.

Both throttles fail open, and that is now alerted rather than silent. A Redis outage lifts
the per-account login lockout and the per-address email cap while the request still
succeeds, so each failure path logs `throttle_store_unavailable` naming the operation and
the flow. It is logged at **ERROR**, and that level is the alert: Sentry is initialised
without a `LoggingIntegration`, so the SDK's default `event_level` of ERROR is what turns a
record into an issue, and an issue is the only thing that pages. At WARNING these records
were a breadcrumb on some later event, which meant the brute-force lockout could stay off
for the length of an outage with nothing raised anywhere -- the request it happened during
returns normally, so there is no other symptom to notice. The accepted risk is unchanged;
what changed is that it now announces itself.

The level alone is not the whole alert, because the project's only other rule fires on
*high priority* issues and Sentry does not necessarily rank a logged error that high. A
dedicated rule, **"Fail-open throttle: store unavailable"** on the `python-fastapi`
project, matches any event whose message contains `throttle store unavailable` and
notifies on a new issue, a regression, **or** five events in an hour. That last condition
is what covers a second outage weeks later: by then the issue is neither new nor a
regression, and a rule without it would stay silent exactly when the lockout is off again.

The same applies to the revocation store, which fails *closed*: its errors surface to the
caller as a plain 401, so `revocation_store_unavailable` is the only thing separating a
Redis outage from a wave of bad tokens.

Unhandled errors hit a catch-all `500` handler and, when `SENTRY_DSN` is configured, Sentry.

Two separate switches keep credentials out of the tracker, and both are needed.
`send_default_pii=False` drops the client IP, cookies, headers, and request bodies.
`include_local_variables=False` drops the frame locals of every traceback frame, which
`send_default_pii` does not cover and which default to on: the auth handlers bind the parsed
request body to a local, so with locals enabled a fault anywhere under `register`,
`change-password`, or `reset-password` would ship `repr()` of that model -- the plaintext
passwords, or a reset token that is still redeemable -- to the tracker. Sentry's own scrubber
does not catch this, because it matches local *names* against a denylist and the leaking
local is called `data`. As a second layer, the credential fields in `api/schemas/auth.py` are
declared `repr=False`, so those values stay out of any `repr()` regardless of who calls it.

The browser SDK needs its own guard, since the reset link carries its token in the query
string: `frontend/src/main.tsx` installs `beforeSend` and `beforeBreadcrumb` hooks
(`frontend/src/lib/sentry.ts`) that redact `token`, `access_token`, and `refresh_token`
from event URLs and from navigation and fetch breadcrumbs.

Those hooks were inert until this was fixed. `frontend/Dockerfile` declared only
`ARG VITE_API_URL`, so `VITE_SENTRY_DSN` never reached the Vite build even though it was
set on all three frontend services; the `if (import.meta.env.VITE_SENTRY_DSN)` guard in
`main.tsx` folded to `false` and the whole `Sentry.init` call was tree-shaken out of every
deployed bundle. No browser error was reported from any environment. The scrubbers now run
because the SDK actually initialises -- so they are worth re-reading as live code rather
than as documentation of an intent.

## Secrets

Configuration comes from environment variables; the local `.env` is gitignored and never
committed, and deployment secrets live in Railway variables rather than in the image. CI
runs `detect-secrets` against a committed baseline, and the same check runs locally before a
push, so a credential added to the tree is caught before it leaves the machine.

Rotating the `become_app` database password without downtime uses a second credential so
there is never a window where the application cannot connect:

1. Create a replacement login with the same grants -- `CREATE ROLE become_app_v2 LOGIN ...`,
   then apply the `scripts/db/roles.sql` grants to it.
2. Point the environment's `DATABASE_URL` at `become_app_v2` in Railway and redeploy.
3. Confirm health is `200` and that `pg_stat_activity` shows connections from the new role.
4. Drop the old role: `DROP ROLE become_app;`. Rename `become_app_v2` back during a later
   quiet window if you want the canonical name restored.

`SECRET_KEY` rotates the same way: add the new value, redeploy, verify, then remove the old
one. Rotating it invalidates every existing session, which is the point when a leak is
suspected.

## GDPR: export and erasure

Both data-subject rights are served by the API. Export (Article 20) returns the full
personal dataset as JSON from `GET /api/v1/users/me/export`. Erasure (Article 17) is handled
by `DELETE /api/v1/users/me`: the request carries a disposition for every project the user
still admins -- transfer it to another member, or delete it -- and the account is removed
only once each owned project has been dealt with. That keeps one person's erasure from
silently taking a whole panel's opinions with it. The profile-photo blob is deleted from
object storage as part of the same operation, so erasure covers stored media too.

When an admin removes a member from a project, that member's opinion is deleted in the same
transaction and the project result is recalculated without it (`remove_member` in
`api/services/project_membership_service.py`). Otherwise the row would outlive the
membership: it carries the person's name, email, and stated position, it is served to every
remaining member and embedded in every export, and `RequireProjectAccess` would no longer
let the person concerned withdraw it themselves.

## Accepted risks

Seven properties are known, deliberate, and reviewed. They are recorded here so a future
audit does not re-litigate them.

**Inviting by email discloses whether an address has an account.** Inviting an address that
has no account answers `404`, which is inherent to the flow: an invitation cannot be created
for a user row that does not exist. The bit disclosed is one the caller already supplied, and
the caller is an authenticated project admin rather than an anonymous prober. Registration
used to disclose the same bit through a `409`; deferred activation closed it (see
"Registration and email verification" above).

**A stranger's signup still puts an activation link in your inbox, and it looks like any
other.** Pre-registering somebody else's address is not something an unauthenticated endpoint
can prevent, and the mail it triggers comes from us, to you, worded exactly as your own
would be. What it no longer does is anything: following it requires the password behind the
submission, which the stranger chose and you do not know, so the link is inert in your hands
and unreachable in theirs (see "Registration and email verification" above). The residue is
one unexplained email, plus a pending unverified account holding your address. Registering
normally, or completing a password reset, takes the address over for login and kills every
outstanding link -- though not the display name it was pre-registered under; see the next
entry. Nothing about it is worth acting on, but a support question about "why did I get this"
is a legitimate one and the answer is here.

**Reclaiming a pre-registered account through a resend or a reset keeps the name it was
pre-registered under.** `create_resend_url` takes `first_name`/`last_name` from the account
row, and a completed password reset never touches them either -- both confirm the address
and let the new owner set the account's password, but neither writes a name. If a stranger
pre-registered the address under a name of their choosing, that name is what
`GET /auth/me` returns afterwards, and what surfaces in project member lists and invitations,
until the account holder does one of two things: register the address again (which does write
the submitter's own names, the same as a free address) or edit the profile once signed in.
Only re-registering closes this in the same step that reclaims the credentials; a resend or a
reset does not.

**`POST /auth/register` still has a timing signal, of one bit and only once.** A submission
whose email is suppressed by the per-address budget skips an awaited round trip to the mail
provider, so it comes back measurably sooner than one that sends. A first probe can therefore
learn that mail was recently triggered for that address. It is weak and self-consuming: the
probe is itself a submission, so it spends from the same budget and changes the answer the
next probe gets, and it reports on recent activity rather than on whether an account exists
-- every branch spends a slot, so no sequence of probes separates a free address from a taken
one. `POST /auth/resend-verification` has the narrower version of the same property: it
awaits a send only when the address has a pending signup, so a first probe against a clean
budget distinguishes that case. Closing either means making the send fire-and-forget, which
is the same queue change `forgot-password` needs for the identical property.

**A stranger who knows a pending address can use up its daily activation mail.** The budget is
per address and shared by every send the flow can trigger, which is what stops an inbox being
flooded. The cost is that anyone who knows an address with a signup already pending can spend
the day's five unauthenticated `resend-verification` calls against it, after which the account
holder's own resend, and their own re-registration, mail nothing while still answering the
usual `202`. It cannot be closed by checking the password first, because the check would
itself become the oracle the uniform response exists to remove. It is not a wedge: whatever
link was mailed before the drain still works, and `forgot-password` draws on a separate budget
and now confirms the address on success, so a password reset gets the holder in regardless.
Support's answer to "I asked for the email again and nothing came" is to use forgot password.

**A Redis outage lifts the per-address email caps.** `RedisEmailSendThrottle` answers `True` on
a `RedisError` (`api/auth/email_throttle.py`), so while the store is unreachable neither the
60-second cooldown nor the five-a-day total applies to `forgot-password`, `register`, or
`resend-verification`, and someone rotating source addresses can put more mail in one inbox
than the cap allows. The fail-open predates deferred activation and was written for recovery:
a store hiccup must never be able to swallow a password-reset email. Deferred activation
widened its reach, since registration and resend now draw on the same throttle, so an outage
now lifts the cap on activation mail as well. Failing closed is the worse trade. These
endpoints answer the same `202` whether or not mail went out, so a closed throttle would stop
every signup and every reset silently for the duration -- the acknowledgement would look
normal, nothing would arrive, and no error would be raised to alert on. The flood it would
prevent stays bounded meanwhile: the per-IP limiter survives a store outage by falling back to
slowapi's in-memory storage, which caps each source at `LIMIT_FALLBACK`, 60 requests a minute
per instance (looser than the 3 and 5 a minute those routes normally carry, so the outage does
widen this too). Redis is a hard requirement in every deployed profile, so an outage here is
short and is already paging someone. Handing the fallback to `InMemoryEmailSendThrottle`
instead was considered and dropped: it keeps a dict entry per address it has seen and never
evicts one, which would open a memory-growth path during exactly the outage it was meant to
cover.

**Login and refresh also return the refresh token in the JSON body.** The browser client
never reads it -- it uses the `HttpOnly` cookie -- but programmatic clients can only obtain
the token this way, and `POST /auth/refresh` accepts it in the request body for exactly that
reason. Reading the body value requires script execution on the origin, which the CSP
(`script-src 'self'`), the explicit CORS allow-list, and `SameSite=Strict` are there to
prevent; rotation with reuse detection then caps the value of a token that does leak.

## Database

How the PostgreSQL databases are locked down. This layer sits under the application and is
operated through its own runbooks.

### Roles and least privilege

Every environment's database is reached through two roles, never one:

- **`become_app`** -- the application runtime role behind `DATABASE_URL`. It is a plain login
  role: `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOBYPASSRLS`. Its rights stop at
  `SELECT/INSERT/UPDATE/DELETE` on the application tables plus `USAGE`/`SELECT` on their
  sequences. It cannot run DDL, create objects in `public`, or read another role's data.
- **`postgres`** -- the Railway-provisioned superuser, used only by Alembic for schema changes
  through `MIGRATION_DATABASE_URL`. Railway hands out exactly one superuser, so there is no
  separate `migrator` role; keeping migrations on a distinct URL is what isolates DDL from the
  runtime token, without the overhead of in-session `SET ROLE`.

`scripts/db/roles.sql` is the idempotent source of truth for this setup. Running it against an
environment as `postgres` reconciles the grants, the default privileges that hand every future
Alembic-created table to `become_app`, the `REVOKE CREATE ON SCHEMA public FROM PUBLIC`
lockdown, a pinned `search_path` (`pg_catalog, public`, which closes CVE-2018-1058 for the
exposed role), and the role-level `statement_timeout`/`idle_in_transaction_session_timeout`/
`lock_timeout`. Passwords stay out of the file -- they live in Railway variables.

The connection itself is hardened in `api/db/engine.py`: TLS is required on deployed databases
(`sslmode=require`), each connection is tagged with an `application_name`, and the per-session
statement and idle-in-transaction timeouts are also set client-side through libpq `options`, so
a single runaway query cannot monopolise the database.

### Network exposure

Production and staging databases answer only on Railway's private network
(`*.railway.internal`); their public TCP proxies were removed, so a leaked password is not the
sole barrier between the internet and the data. The dev database is the one exception, and even
there the proxy is normally closed -- it is opened in the Railway dashboard only for a specific
hands-on operation and shut again afterwards. That toggle is the project's substitute for an IP
allowlist, which Railway's platform does not offer.

### Audit logging

Railway's managed Postgres permits `ALTER SYSTEM`, so connection auditing is enabled directly on
each database and reloaded without a restart:

```sql
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';
ALTER SYSTEM SET log_statement = 'ddl';
ALTER SYSTEM SET log_min_duration_statement = '5000';
SELECT pg_reload_conf();
```

Connections and disconnections are recorded, every DDL statement is logged -- schema changes
should only ever originate from Alembic, so anything else here is a red flag -- and statements
slower than five seconds are captured. The output flows into the Railway service logs. Finer
read/write auditing would need the `pgaudit` extension, but that requires
`shared_preload_libraries`, which Railway's image does not expose; `log_statement = 'ddl'` is the
workable substitute.

### Backups

Railway's managed backups require the Pro plan, so on the current (free) plan the Postgres
volumes are **not** backed up automatically. Until that changes, take manual dumps with
`scripts/db/backup.sh`, which opens a temporary proxy, runs `pg_dump`, and removes the proxy
again:

```bash
./scripts/db/backup.sh prod      # writes backups/prod-<timestamp>.dump
```

Run it before risky migrations and on a regular cadence. The dumps stay out of the repo
(`backups/` is gitignored -- they contain user data). Restore into any database with:

```bash
pg_restore --no-owner --no-privileges -d <target-url> backups/<dump>
```

Upgrading the prod service to the Railway Pro plan would replace this with scheduled backups
plus point-in-time recovery.

## Data integrity and migrations

Deleting a user must not silently destroy other people's work. Most child rows clear
themselves through `ON DELETE CASCADE` (memberships, opinions, sent and received
invitations, reset tokens, activation tokens). A project a user **admins** is shared
data, so `projects.admin_id` uses `ON DELETE RESTRICT`: the database refuses to orphan
or silently erase a shared project, which is why the erasure endpoint requires an
explicit disposition for each one (see [GDPR](#gdpr-export-and-erasure)). Schema changes
ship as reversible Alembic migrations run through the migration-only superuser URL,
keeping DDL off the runtime role.
