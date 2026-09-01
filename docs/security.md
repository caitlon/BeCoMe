# Security

What is actually implemented in BeCoMe to keep the product and its users' data safe, and how
to operate the pieces that need runbooks. This is a description of the running system, not a
wishlist. Deployment topology lives in [`environments.md`](environments.md). The academic
threat model (attack trees, residual-risk argument) lives in the thesis workspace, and this
page does not repeat it.

## Contents

- [Status at a glance](#status-at-a-glance)
- [Authentication](#authentication)
- [Registration and email verification](#registration-and-email-verification)
- [Session transport (cookies and CSRF)](#session-transport-cookies-and-csrf)
- [Authorization and tenant isolation](#authorization-and-tenant-isolation)
- [Rate limiting and abuse control](#rate-limiting-and-abuse-control)
- [Input validation](#input-validation)
- [Configuration and profiles](#configuration-and-profiles)
- [Network and edge](#network-and-edge)
- [Logging, observability, and privacy](#logging-observability-and-privacy)
- [Secrets](#secrets)
- [GDPR: export and erasure](#gdpr-export-and-erasure)
- [Accepted risks](#accepted-risks)
- [Database](#database)
- [Data integrity and migrations](#data-integrity-and-migrations)

## Status at a glance

| Area | Status | Where |
|------|--------|-------|
| Authentication: JWT, refresh rotation, lockout | Implemented | `api/auth/` |
| Session transport: HttpOnly cookies + CSRF | Implemented | `api/auth/cookies.py`, `api/middleware/csrf.py` |
| Authorization and tenant isolation | Implemented | `api/dependencies.py` |
| Rate limiting and abuse control | Implemented | `api/middleware/rate_limit.py` |
| Input validation | Implemented | `api/schemas/` |
| Configuration invariants per profile | Implemented | `api/config.py` |
| Network and edge: Cloudflare, CORS, headers | Implemented | `api/main.py`, Cloudflare |
| Logging, observability, and PII scrubbing | Implemented | `api/logging_config.py`, `api/logging_context.py` |
| Secrets management and rotation | Implemented | Railway variables, [below](#secrets) |
| GDPR export and erasure | Implemented | `api/routes/users.py` |
| Database least-privilege, network, auditing | Implemented | `scripts/db/`, `api/db/engine.py` |
| Automated database backups | Partial, manual dumps | `scripts/db/backup.sh` |

## Authentication

Every route path below is relative to the `/api/v1` prefix the routers carry.

Sessions are stateless JWTs signed with `SECRET_KEY` (HS256). Login returns a short-lived
access token and a longer-lived refresh token. Refresh tokens rotate: each refresh mints a
fresh pair tied to a rotation family (a `sid` claim). The API treats the reuse of an
already-rotated refresh token as theft and revokes the entire family, so a stolen token
stops working the moment the legitimate client refreshes. A refresh token minted before the
session model carries no `sid`, and `/auth/refresh` migrates it rather than rejecting it: the
route revokes the old `jti` and starts a fresh family, so its holder keeps a working session.
Changing the password stamps a
per-user cutoff that rejects every token issued before it. Both the change and the reset
route record that cutoff *before* they write the new password, so a revocation-store fault
aborts the operation instead of leaving a fresh password with every old session still alive.
The cutoff itself expires an hour after the longest-lived token would have, so the store
does not keep it forever.

bcrypt hashes the passwords. Because bcrypt silently truncates input at 72 bytes,
`api/auth/password.py` pre-hashes the password with SHA-256 and base64-encodes it first,
which is the approach bcrypt's own maintainers recommend. Registration and password change
both enforce a strength policy.

The login endpoint closes two abuse paths. Repeated failures lock the account for a cooldown
window (`api/auth/login_throttle.py`), which stops online brute force and credential
stuffing against a single account. An unknown email still runs a dummy hash, so a
wrong-email response takes the same time as a wrong-password one. Login timing therefore
reveals nothing about which addresses have accounts.

## Registration and email verification

Registration creates the account unverified, and nobody can log in to it until the address
is confirmed. Login checks `email_verified_at` only *after* the password verifies, and
answers `403`. Checking first would answer differently for an address that has an account
and one that does not, which is the enumeration oracle the uniform `401` exists to prevent.

`POST /auth/register` always answers `202` with one fixed body. Behind it,
`RegistrationService` picks one of three branches: a free address creates an unverified
account, a taken-but-unverified address writes nothing at all, and a taken-and-verified
address stays untouched while its owner gets a notice that someone tried to sign up with it.

**A demo service account answers as a fourth kind of address, without needing a fourth
branch.** Thirteen such accounts hold the opinions of every user's seeded example project
(`is_demo` on `users`, `api/data/example_project.py`), and `select_account_by_email`
(`api/services/query_helpers.py`) excludes them from every lookup that resolves an address:
login, registration, invitation, password reset, and activation resend alike, so each of
those five paths answers a demo address exactly as it answers one nobody has ever
registered. Registration therefore reads it as free: `_create_account` attempts the insert,
loses it to the unique index the demo row already occupies, and falls through the same
`IntegrityError` handling a race between two real submissions takes
(`api/services/registration_service.py`), landing on the uniform `202` with nothing to
activate. The exclusion is what makes this a security control rather than a display
convenience. A lookup that forgot it would let an outsider invite a demo account into a real
project or, had the migration not also inserted every demo row already verified, claim one
outright through the taken-but-unverified branch and read every project it sits in. Both
defenses hold independently: `is_demo` filtering keeps the accounts from being found at all,
and pre-verification means even a lookup that did find one could not fall into the branch
that mints it an activation token.

**A submission is bound to the link it mints, never to the account.** The activation token
carries the submitted password hash and names (`email_verification_tokens`, all three
columns `NOT NULL`), and the account receives them only when somebody redeems that specific
token. The alternative, storing the newest submission on the account row, is an
unauthenticated account-takeover primitive: whoever submits last would decide what every
outstanding link opens, so an attacker submits `victim@example.com` after the real owner
signed up, the owner clicks the link they already have, and the account activates on the
attacker's password.

**Redemption also requires the password the token carries.** `POST /auth/verify-email` takes
`{token, password, language}` and checks the password against the token's `hashed_password`,
never against the `users` row. That is what closes the class the binding above only narrows.
Anyone can cause an activation link to arrive at an address they do not control: a repeat
registration puts a fresh one at the top of the victim's inbox, and nothing distinguishes it
from their own. With the password required, the stranger's link is dead in both hands: the
recipient does not know the submitted password, and the submitter never sees the link. The
victim's own link, with the victim's own password, still works. Neither party can activate
the other's submission.

Three consequences follow. Issuing a link does **not** retire the outstanding ones, unlike
password reset: several live links for one unconfirmed address is the correct state, since
each is single-use and carries its own submission, and retiring them is exactly how one
submitter would kill another's pending link. The API refuses redemption once the address is
verified, with the same opaque `400` an unknown token gets: a token minted while the account
was unconfirmed carries a password, so redeeming it afterwards would rewrite the credentials
of an account somebody is already using, and refusing before it weighs the password also
keeps the endpoint from locking a live account out of its own login. And a completed
password reset sets `email_verified_at` too, which retires every outstanding activation link
in one move. A reset link proves control of the address exactly as an activation link does,
so reclaiming an address somebody pre-registered is one step for the credentials. It is not
one step for the display name. See "Accepted risks" below.

That makes an activation and a reset the two operations that can confirm the same account,
so both go through a `_claim_account` that writes `UPDATE ... WHERE email_verified_at IS
NULL` whenever the row it loaded was still pending, and lets the database pick the winner.
The loser writes nothing and gets the opaque `400`. On the reset side it deliberately leaves
its token unspent, so following the same link again succeeds against the now-confirmed
account. A reset whose account was already confirmed when its token resolved has nothing to
race, because the API refuses an activation redemption once `email_verified_at` is set, so
it writes by id alone. Reading the row and writing it back would instead let a reset that
started while the account was still pending overwrite the password an activation had just
applied, seconds after telling whoever redeemed it to sign in. bcrypt alone holds that
window open for a few hundred milliseconds.

A wrong password answers `403` with its own wording, not the opaque `400` the token errors
share. Whoever reaches that point already holds a live link, so admitting the link is fine
tells them nothing new, while telling a user who mistyped that their link is broken would
send them round the loop asking for another one that would fail the same way. The endpoint's
own per-token lockout (`api/auth/login_throttle.py`), namespaced apart from the one `/login`
uses, caps the guessing oracle that opens: only someone who already holds a live token can
trip it, so a run of failed logins, which anyone who knows the address can produce, can
never deny someone their own activation.

**The lockout keys on the token's hash, not the account.** Issuing a link never retires an
earlier one (see above), so one unconfirmed address can carry several live tokens at the
same time. A single bucket shared by all of them would reopen, one level down, the same
shape of denial the login/activation split above already prevents: anyone who obtains a
single token, forwarded by its recipient or intercepted rather than read from the mailbox
itself, could spend the account's entire activation budget against it and, because every
failure refreshes the window, keep it spent indefinitely, locking the real owner out of a
different, freshly resent link they hold instead. Keying on the token confines that damage
to the token somebody spent it against. It does not widen what one token exposes to
guessing: any single token still allows at most ten activation failures against its own
password, the same bound described below. Nor does it hand an attacker more guesses to
spend: `resend-verification` only ever mints a token carrying the password its own caller
submitted, and the mail carrying it goes to the account's address, not back to whoever
asked, so minting more tokens never buys a guess against a password the caller does not
already know.

**The two budgets are independent, and they add up.** Each endpoint allows 10 failures per
15 minutes and consults only its own counter, login's keyed per account and activation's per
token. The lock fires on the tenth recorded failure, and each endpoint consults it before it
evaluates the password, so each endpoint still evaluates ten guesses: twenty wrong passwords
reachable against that token's password inside a window. A shared counter is the only thing
that would bound the total, and a shared counter is exactly what the split exists to
prevent. Moving the login counter takes no credential and every failure refreshes its
expiry, so a stranger who knows nothing but the address can hold any endpoint that reads it
shut indefinitely. Moving the activation counter takes a live single-use token, and that
token exists in one place: the mailbox it went to. Whoever reaches the extra ten guesses has
therefore already read the mail, and reading the mail takes the account outright through
`forgot-password` without guessing at anything. The extra guesses hand an attacker a weaker
capability than the one they used to get them. A mismatch does still spend from the login
counter, which costs the guesser rather than bounding them: ten activation mismatches lock
`/login` too, so the total only grows when the login guesses come first. `POST
/auth/reset-password` clears the login lockout on success, so an attacker's failed guesses
cannot keep an account locked out of login after its owner has proven control of the address
and set a new password.

The notice mail carries a static `/forgot-password` link, never a minted reset token: an
unauthenticated registration attempt must never mail anyone a working reset link.

The flow closes two side channels alongside the response body. Every branch runs bcrypt on
the submitted password, including the one that writes nothing, so none gives itself away by
answering hundreds of milliseconds faster. And the emails the flow can trigger share one
per-address budget (`api/auth/email_throttle.py`, keyed by a hash of the address), so
submitting a victim's address in a loop from rotating IPs cannot flood the inbox past the
per-IP limiter. Suppression never changes the response.

Every send spends from that budget, including the one on the branch that creates the
account, which is the only branch never *denied* by it. The distinction matters in both
directions. Never denied, because that branch fires at most once per address (a second
submission is by definition no longer free), so charging it would let a stranger drain the
allowance with five unauthenticated `resend-verification` calls and pre-empt a signup that
has not happened yet: the victim would register, get the normal `202`, receive nothing, and
hold an account that cannot log in. Still spending, because a send that left the budget
clean would make two back-to-back submissions separate a free address from a taken one, the
free one mailing on both probes and the taken one going quiet after the first, and the
awaited round trip to the mail provider is exactly the difference the uniform `202` exists
to hide. A resend request for an address with nothing to send spends nothing, for the same
anti-denial reason as the creating branch, and it mails nothing either, so it opens no
timing difference.

Activation tokens otherwise follow the password-reset design: `secrets.token_urlsafe(32)`,
only the SHA-256 hash stored, single use, expiring after
`EMAIL_VERIFICATION_TOKEN_TTL_HOURS` (24 by default). Unknown, spent, and expired tokens all
get one opaque `400`. `POST /auth/resend-verification` takes `{email, password}` and answers
`202` identically for an unknown address, an unverified one, and an already-verified one.
Taking the password makes it a repeat registration minus the names: the link it mails
carries that password like any other, and the names come from the account, which is all a
resend request can know. An address-only resend would mint a link with nothing to prove,
which anyone receiving the mail could follow.

Before any of that touches the database, the submitted address goes through
`EmailAddressPolicy` (`api/services/email_policy.py`): a vendored disposable-domain
blocklist and an MX/A/AAAA reachability check that fails open. Only a definitive negative
rejects: NXDOMAIN, a confirmed absence of every record type, or an RFC 7505 null MX, which
is the domain itself declaring that it accepts no mail and which overrides the A/AAAA
fallback the way the RFC requires. Both verdicts depend only on the domain string, never on
database state, so their `400` leaks nothing about account existence. Each has a runtime
kill switch (`DISPOSABLE_EMAIL_BLOCKING_ENABLED`, `MX_CHECK_ENABLED`) in case either starts
rejecting real users.

**`language` on `/auth/verify-email` carries no authority and needs none.** A successful
redemption seeds the newly activated account's example project
(`ExampleProjectService.seed_for`), and `language` only picks which pre-written variant of
that project's text gets seeded. The request schema constrains it to the `Literal["en",
"cs"]` the seeded copy actually ships in, so it never reaches the database as free text and
cannot widen anything the token/password pair above already decided. Seeding runs after
activation succeeds, and the route swallows its failure (`api/routes/auth.py`): an account
that verified but got no example project is an acceptable outcome, an account nobody can log
in to because seeding raised is not.

## Session transport (cookies and CSRF)

The browser client keeps no token in JavaScript-readable storage. Login and refresh set the
access and refresh tokens as cookies marked `HttpOnly`, `SameSite=Strict`, and `Secure`. An
XSS payload therefore cannot read the session the way it could read `localStorage`.

The names carry prefixes the **browser** enforces: `__Host-access_token`,
`__Host-csrf_token`, `__Secure-refresh_token`. `__Host-` is the one that matters: the
browser accepts a cookie under that prefix only with `Secure`, `Path=/` and no `Domain`, and
only the exact host it belongs to can write it. That closes the gap `SameSite` leaves open:
a page on any sibling `becomify.app` subdomain counts as same-site here, so without the
prefix it could write a session cookie of its own and log the victim into the attacker's
account (session fixation). That is a different attack from the CSRF one below, and one no
amount of token derivation prevents. The refresh cookie takes `__Secure-` instead, because
`__Host-` would force `Path=/` and hand it to every request on the site rather than the auth
routes alone.

Two consequences worth knowing. `Secure` is now unconditional rather than following the
request scheme: a `__Host-` cookie without it is not a weaker cookie, it is one the browser
discards. And the deletions in `clear_auth_cookies` carry the same attributes, because a
deletion is a `Set-Cookie` like any other. The browser rejects one sent without `Secure`
outright, and logout would answer `204` with the session cookie still in place.

That is also why the e2e suite runs over HTTPS (`frontend/scripts/e2e-cert.mjs` mints a
throwaway certificate). Browsers treat `localhost` as a secure context and accept Secure
cookies there, except WebKit, which refuses to store them over plain `http://localhost` at
all, so on HTTP every authenticated Safari-engine test would fail on a cookie that was never
stored. Verified across all three engines before adopting the prefixes.

`SameSite=Strict` already stops the session cookies from riding along on cross-site
requests. On top of that, a CSRF check (`api/middleware/csrf.py`) defends the same-site
case, and the case `SameSite` does not cover at all: "site" means the registrable domain, so
a page on any `becomify.app` subdomain is same-site with the API and its requests do carry
the session cookies.

The token is **derived from the session**, not drawn at random and stored beside it:
`csrf_token_for(sid)` is an HMAC of the session id under the application secret
(`api/auth/cookies.py`). On a mutating request the middleware reads the session cookie,
takes the `sid` from it, recomputes the expected token, and compares it against the
`X-CSRF-Token` header. That comparison is against a value the server derives, never against
something the client sent.

The difference matters against an attacker who can write cookies for the API host, one
sitting on a sibling `becomify.app` subdomain, since a cookie set with `Domain=becomify.app`
shadows ours. A plain cookie-versus-header comparison loses to that attacker twice: they can
plant a value they know in the `csrf_token` cookie and echo it in the header, and they can
equally plant a token minted for a session they legitimately hold. Binding the token to the
victim's `sid` closes both, since forging one for a session you do not hold means forging an
HMAC.

Deriving it also means omission cannot waive the check. It keys on the *session* cookie, so
it checks any request that authenticates as somebody, where the old comparison armed itself
on the presence of the CSRF cookie and silently passed anything arriving without it. The
check skips bearer-token clients, which carry no session cookie, and every path under
`/api/v1/auth/` except logout. That is a prefix rule rather than a list, so a new auth route
is exempt by default. A stale cookie left by a revoked session can never block a fresh
login. Logout stays CSRF-protected.

Reading the `sid` deliberately skips expiry, revocation, and the per-user cutoff
(`session_id_from_access_token`). It still verifies the signature, but the rest is the
authentication layer's job, and checking it here would put three Redis round trips in front
of every mutating request. A token failing any of them runs into that refusal moments later
anyway, with the CSRF check already applied.

The SPA gets the value from a response header rather than from the cookie. Login and refresh
send it in an `X-CSRF-Token` **response** header, and `GET /auth/me`, the app's session
probe on mount, reports the token for the session it authenticates as, so a page reload
recovers it (`api/auth/cookies.py::set_csrf_header`). The header is what makes this workable
on the deploys: the cookie carries no `Domain` attribute, so it belongs to the API host, and
the app runs on a different one, where `document.cookie` shows it nothing while the browser
keeps sending it. Reading the cookie still works when the two share an origin, which is how
local development runs behind the Vite proxy, and stays the fallback. `CORSMiddleware` names
the header in `expose_headers`. Without that the browser withholds it from cross-origin
JavaScript.

Handing the value back changes nothing about the guarantee. The client that owns the session
is meant to read it, and CORS answers against an explicit origin allow-list, so a hostile
origin can no more read the header than the cookie. Widening the cookie with
`Domain=becomify.app` would look like the smaller fix and is the one to avoid: dev, staging,
and production all sit under that parent and would overwrite each other's token, breaking
whichever the user visited last. Deriving the token also retired a sharp edge on `/auth/me`,
which used to echo the caller's own cookie back: Starlette's RFC 2109 cookie unescape turns
`csrf_token="\012..."` into a real newline, and uvicorn writes response headers without
validating them, so that echo was a response-splitting primitive kept in check by a filter.
There is no client value on that path any more.

The other half of the same threat is an attacker on a sibling subdomain shadowing the
*session* cookie rather than the CSRF one, which logs the victim into the attacker's account
instead of forging a request. The `__Host-` prefix described at the top of this section
covers that half. Deriving the CSRF token would not have helped there: the two defenses
answer two different attacks, and the product needs both.

The `Authorization: Bearer` path stays alongside the cookie path for programmatic clients
and the test suite. It authenticates the same tokens without the cookie or CSRF machinery.
Such a client sends no session cookie, so it gets no header back either.

## Authorization and tenant isolation

BeCoMe is multi-tenant: every project-scoped route runs through `RequireProjectAccess`
(`api/dependencies.py`) before it reads or writes anything. A caller who is not a member of
the project gets `404 Not Found`, the same answer as a project that does not exist, so the
API never confirms the existence of a project to someone with no business knowing about it.
A member who lacks the required role (an expert attempting an admin action) gets `403`,
since they already know the project is there. The API logs each denial with the project and
user id for audit.

Row-level security is deliberately off (migration `c83186b79ad7`): the tables arrived from
Supabase with RLS enabled and forced but no policies, which is a no-op for a superuser and a
total lockout for the least-privilege `become_app` role. Authorization therefore has no
database backstop, since if a route does not check then nothing does, so
`tests/unit/api/test_route_authorization.py` enforces it structurally instead of trusting
review. It walks the application's real route table and asserts two things: every route
taking a `project_id` has `RequireProjectAccess` somewhere in its dependency tree, and every
route taking *any* path parameter is either guarded the same way or listed in
`UNGUARDED_BY_DESIGN` with the check that stands in for the dependency.

The second guard exists because the first cannot see the routes that matter most here: an
identifier like `{invitation_id}` points at somebody else's record just as squarely as a
project id does, and carries no `project_id` for the first check to notice. Three routes are
exempt today: the public avatar proxy, and accepting or declining an invitation, where
`InvitationService` compares `invitee_id` against the caller because there is no membership
to check until the invitation is accepted. A new route naming an object fails the suite
until somebody either wires in the dependency or records what replaces it.

## Rate limiting and abuse control

slowapi handles rate limiting, backed by Redis, with an in-memory fallback when Redis is
unreachable (`api/middleware/rate_limit.py`). Two global ceilings apply to every route,
`300/minute` and a `20/second` burst, so every endpoint stays bounded even if it forgot its
own limit. On top of that, routes carry tighter limits by risk:

| Limit | Value | Applied to |
|-------|-------|-----------|
| Auth | `5/minute` | Login, register, refresh |
| Password reset | `3/minute` | Forgot and reset password, verify and resend verification, change password |
| Write | `30/minute` | Submitting and withdrawing an opinion, inviting a member |
| Upload | `10/minute` | Photo upload |
| Standard | `60/minute` | GDPR export, standalone calculate, result export |
| Photo | `120/minute` | The public avatar proxy, which a page loads once per member |

Only those routes carry a decorator. Everything else is bounded by the two global ceilings
alone, which is the point of having them.

The limiter keys on the real client IP, and the rule is not hop-based. `get_client_ip`
(`api/utils/client_ip.py`) reads `CF-Connecting-IP` only when the request carries the
`X-Origin-Verify` header matching `CLOUDFLARE_ORIGIN_SECRET`. Anything else, including a
deployed service with no secret configured, keys under one constant. It never reads
`X-Forwarded-For`, so a client cannot spoof its way around the per-IP limits. Rate limiting
fails **open**: `swallow_errors` and an in-memory fallback keep a Redis outage from refusing
traffic, at the cost of the shared counters. See "Accepted risks" for the reasoning. A
request body over the configured ceiling gets a `413` before anything buffers it, and the
API streams profile-photo uploads under a size cap rather than reading them whole into
memory.

A photo upload passes three independent checks (`api/services/storage/validation.py`): the
declared content type must be one of four image types, the leading magic bytes must match
that declaration, and the pixel canvas must fit the avatar budget (4096x4096, no side over
8192). The last one exists because bytes and pixels are not the same limit: image formats
compress uniform areas so well that a 35 KB PNG can declare a 25-megapixel canvas, which
costs tens to hundreds of megabytes the moment anything decodes it, depending on the mode.
The validator parses only the header, so rejecting such a file costs nothing.

## Input validation

Request DTOs are Pydantic models with `extra="forbid"` (`api/schemas/`), so an unexpected
field draws a `422` rather than passing as a silently ignored parameter. String fields carry
length caps, free-text names go through HTML sanitization, and list endpoints clamp their
page size (`MAX_PAGE_SIZE = 100`, `api/pagination.py`) so a single request cannot ask the
database for an unbounded result set. The GDPR export is the one deliberate exception to the
list caps, since Article 20 requires the full dataset. `api/README.md` records the
exemption, and the route itself carries no note.

## Configuration and profiles

The app runs under one of three profiles selected by `APP_ENV`: `dev`, `test`, `prod`
(`api/config.py`). A deploy must satisfy nine invariants that fail startup rather than boot
insecurely (`_validate_deploy_invariants`): the `SECRET_KEY` must be strong, the guard
refuses SQLite in favor of PostgreSQL, `redis_url` must carry a value,
`cloudflare_origin_secret` must be present, `CORS_ORIGINS` must include at least one
non-loopback origin, `frontend_base_url` must not be a loopback host, since every activation
and reset link builds on it, a real email provider must answer, `DEBUG` must be off, and
`MIGRATION_DATABASE_URL` must carry a value even when it repeats `DATABASE_URL`. All nine
apply to every deploy, production and staging and the Railway dev service alike.

"Deployed" is not the same as "not dev". The dev *service* has its own database and a public
URL, so it meets the same invariants. `is_deploy` decides it in three steps. `prod` always
counts, even on a laptop. `test` counts unless `TESTING` is set, which is what holds staging
to the invariants and exempts the pytest suite. `dev` counts only when a
`RAILWAY_ENVIRONMENT_NAME` marks it as a deploy, and again only when `TESTING` is unset. A
laptop and a CI runner carry no such marker, so the invariants guard staging without
breaking the local suite. The app serves the interactive API docs (`/docs`) only outside
production.

## Network and edge

The public origin is `becomify.app`, served through Cloudflare, and each deployed
environment has its own host under it: `api.becomify.app` (production),
`api-harbor.becomify.app` (staging), `api-atelier.becomify.app` (dev). A Cloudflare
Transform Rule per host injects a shared secret header the origin then requires
(`cloudflare_origin_secret`, a different value per environment, demanded of every deploy by
`Settings._validate_deploy_invariants`).

The lock decides what the origin *believes*, not what it *accepts*. Railway also gives each
service a `*.up.railway.app` address, and those answer, so a caller can still bypass the
edge. What the secret buys is that a request arriving without it keys under a single
constant rather than off a forwarding header the origin cannot vouch for
(`api/utils/client_ip.py`). That matters because uvicorn runs with `--proxy-headers
--forwarded-allow-ips='*'`, which makes `request.client.host` only as trustworthy as
whatever wrote `X-Forwarded-For`. It also makes the rate-limit key correct rather than just
safe: without the lock, a deployed service keys every request under one constant, collapsing
all callers into a single bucket, because it can trust neither `CF-Connecting-IP` nor the
transport peer. Closing the bypass itself, so nobody can skip the WAF and bot rules, means
retiring the `*.up.railway.app` domains, which is still open. CORS carries explicit allowed
origins and `allow_credentials=True` (required for the cookie session). It permits the
`X-CSRF-Token` header on the way in and exposes it on the way out, since the SPA reads the
CSRF token off the response.

Both tiers send security response headers: the API from middleware
(`api/middleware/security_headers.py`), the SPA from nginx (`frontend/nginx.conf`). Their
Content-Security-Policies match except where the SPA genuinely needs more. Its `connect-src`
names the API origin, which is cross-origin on the deploys, plus the Sentry ingest hosts the
browser SDK reports to. Its `img-src` names that same API origin, because the API serves
profile photos and `<img>` tags render them, which is an image load rather than something
`connect-src` covers. The Docker build bakes that origin into the policy from the same
`VITE_API_URL` build argument the bundle uses, so the served policy cannot drift from the
URL the app actually calls. `tests/integration/test_frontend_csp.py` asserts both directives
against the config: a CSP that under-permits fails silently, since the browser drops the
request before it reaches the origin and nothing appears in the logs. Both tiers send
`X-XSS-Protection: 0` on purpose: the legacy auditor it enables is unreliable, browsers have
dropped it, and its blocking mode has itself leaked cross-origin information. The CSP is
what constrains injection.

The correlation ID does not travel on trust either. The API echoes an inbound `X-Request-ID`
on the response and writes it to every log record of the request, so it reuses one only when
it looks like an ID, meaning a short and conservative alphabet, and substitutes a fresh UUID
otherwise (`api/middleware/request_logging.py`).

## Logging, observability, and privacy

The deployed profiles emit structured JSON. Each request carries an `X-Request-ID`, and a
context filter binds that request id and the acting user id onto every `api.*` log record
through contextvars (`api/logging_context.py`), so a service or security log line traces
back to a request without threading identifiers by hand. Personal data stays out of the
logs: what goes into the record is a truncated keyed digest (`email_hash`), never the
address itself. The key matters, because anyone holding the logs can reproduce a plain
SHA-256 of an address, so they could confirm whether a given person has an account by
hashing a guess. The tag is an HMAC keyed with `LOG_HASH_KEY` (falling back to
`SECRET_KEY`), which makes it meaningless outside the application while still correlating
repeated attempts on one account. Rotating the fallback re-tags every later record, so set
`LOG_HASH_KEY` explicitly where that correlation has to survive a rotation.

The rule for any new log record: identifiers, keyed tags, and counts, never the values
themselves. Allowed are `user_id`, `project_id`, `invitation_id`, `jti`, `sid`, `ip`,
`status_code`, `duration_ms`, `row_count`, and the `reason` for refusing a request. Never
logged, at any level: passwords and password hashes, raw JWTs, the CSRF cookie or header
value, the email API key or bucket credentials, the `Authorization` header, any request or
response body, raw email addresses, activation or reset tokens and the URLs carrying them,
and free-text user content such as a project description.

Two specific traps are worth naming. First, `_digest()` in `api/auth/login_throttle.py` and
`api/auth/email_throttle.py` is a **plain, unkeyed** SHA-256 of the identifier. It exists to
key the store, not to reach a log. Writing it out would rebuild exactly the oracle the key
in `hash_email` prevents, so records in those modules name the flow (`key_prefix`, `op`) and
never the account. The address-scoped event belongs at the call site in
`api/routes/auth.py`, which has the keyed tag. Second, `api/logging_config.py` pins
`sqlalchemy.engine` at WARNING, and that logger must stay above DEBUG on any deployed
service: its DEBUG level prints bound query parameters, which on this schema means bcrypt
hashes, addresses, names, and reset-token hashes shipped to the log drain in the clear. That
pin matters because the dev deploy now runs at `LOG_LEVEL=DEBUG` against a real database.

Both throttles fail open, and that is now alerted rather than silent. A Redis outage lifts
the per-account login lockout and the per-address email cap while the request still
succeeds, so each failure path logs `throttle_store_unavailable` naming the operation and
the flow. Those records go out at **ERROR**, and that level is the alert. The app
initializes Sentry without a `LoggingIntegration`, so the SDK's default `event_level` of
ERROR is what turns a record into an issue, and an issue is the only thing that pages. At
WARNING these records were a breadcrumb on some later event, which meant the brute-force
lockout could stay off for the length of an outage with nothing raised anywhere, since the
request it happened during returns normally, so there is no other symptom to notice. The
accepted risk is unchanged. What changed is that it now announces itself.

The level alone is not the whole alert, because the project's only other rule fires on
*high priority* issues and Sentry does not necessarily rank a logged error that high. A
dedicated rule, **"Fail-open throttle: store unavailable"** on the `python-fastapi` project,
matches any event whose message contains `throttle store unavailable` and notifies on a new
issue, a regression, **or** five events in an hour. That last condition is what covers a
second outage weeks later: by then the issue is neither new nor a regression, and a rule
without it would stay silent exactly when the lockout is off again.

The revocation store fails *closed* instead. A decode-path error surfaces as a plain 401,
while a failed session write on login, refresh, or logout surfaces as a 503 through
`revocation_store_unavailable_handler`, so a Redis outage is visible to the caller either
way. It logs `revocation_store_unavailable` at WARNING rather than ERROR, because the
request already failed and the caller already knows.

Unhandled errors hit a catch-all `500` handler and, when `SENTRY_DSN` carries a value,
Sentry.

Two separate switches keep credentials out of the tracker, and the product needs both.
`send_default_pii=False` drops the client IP, cookies, headers, and request bodies.
`include_local_variables=False` drops the frame locals of every traceback frame, which
`send_default_pii` does not cover and which default to on: the auth handlers bind the parsed
request body to a local, so with locals enabled a fault anywhere under `register`,
`change-password`, or `reset-password` would ship `repr()` of that model to the tracker,
meaning the plaintext passwords, or a reset token that is still redeemable. Sentry's own
scrubber does not catch this, because it matches local *names* against a denylist and the
leaking local goes by `data`. As a second layer, the credential fields in
`api/schemas/auth.py` carry `repr=False`, so those values stay out of any `repr()`
regardless of who calls it.

The browser SDK needs its own guard, since the reset link carries its token in the query
string: `frontend/src/main.tsx` installs `beforeSend` and `beforeBreadcrumb` hooks
(`frontend/src/lib/sentry.ts`) that redact `token`, `access_token`, and `refresh_token` from
event URLs and from navigation and fetch breadcrumbs.

Those hooks were inert until a 2026 fix. `frontend/Dockerfile` declared only `ARG
VITE_API_URL`, so `VITE_SENTRY_DSN` never reached the Vite build even though all three
frontend services set it. The `if (import.meta.env.VITE_SENTRY_DSN)` guard in `main.tsx`
folded to `false` and the bundler tree-shook the whole `Sentry.init` call out of every
deployed bundle. No environment ever reported a browser error. The scrubbers now run because
the SDK actually initializes, so read them as live code rather than as documentation of an
intent.

## Secrets

Configuration comes from environment variables. `.gitignore` covers the local `.env`, which
never reaches a commit, and deployment secrets live in Railway variables rather than in the
image. CI runs `detect-secrets` against a committed baseline, and the same check runs
locally before a push, so a credential added to the tree is caught before it leaves the
machine.

Rotating the `become_app` database password without downtime uses a second credential so
there is never a window where the application cannot connect:

1. Create a replacement login with the same grants: `CREATE ROLE become_app_v2 LOGIN ...`,
then apply the `scripts/db/roles.sql` grants to it.
2. Point the environment's `DATABASE_URL` at `become_app_v2` in Railway and redeploy.
3. Confirm health is `200` and that `pg_stat_activity` shows connections from the new role.
4. Drop the old role: `DROP ROLE become_app;`. Rename `become_app_v2` back during a later
quiet window if you want the canonical name restored.

`SECRET_KEY` rotates the same way: add the new value, redeploy, verify, then remove the old
one. Rotating it invalidates every existing session, which is the point when a leak is
suspected.

## GDPR: export and erasure

The API serves both data-subject rights. Export (Article 20) returns the personal dataset as
JSON from `GET /users/me/export`: the profile, owned projects and their results,
memberships, opinions, and received invitations. The export leaves out invitations the user
sent. `DELETE /users/me` performs erasure (Article 17): the request carries a disposition
for every project the user still admins, either transferring it to another member or
deleting it, and the account is removed only once every owned project has one. That keeps
one person's erasure from silently taking a whole panel's opinions with it. The same
operation removes the profile-photo blob from object storage, so erasure covers stored media
too.

When an admin removes a member from a project, `remove_member`
(`api/services/project_membership_service.py`) deletes the membership and that member's
opinion in one transaction, and the route recalculates the project result afterwards
(`api/routes/projects.py`). Otherwise the row would outlive the membership: it carries the
person's name, email, and stated position, it reaches every remaining member and every
export, and `RequireProjectAccess` would no longer let the person concerned withdraw it
themselves.

## Accepted risks

Seven properties are known, deliberate, and reviewed. This section records them so a future
audit does not re-litigate them.

**Inviting by email discloses whether an address has an account.** Inviting an address that
has no account answers `404`, which is inherent to the flow: an invitation cannot be created
for a user row that does not exist. The bit disclosed is one the caller already supplied,
and the caller is an authenticated project admin rather than an anonymous prober.
Registration used to disclose the same bit through a `409`. Deferred activation closed it
(see "Registration and email verification" above).

**A stranger's signup still puts an activation link in your inbox, and it looks like any
other.** Pre-registering somebody else's address is not something an unauthenticated
endpoint can prevent, and the mail it triggers comes from us, to you, worded exactly as your
own would be. What it no longer does is anything: following it requires the password behind
the submission, which the stranger chose and you do not know, so the link is inert in your
hands and unreachable in theirs (see "Registration and email verification" above). The
residue is one unexplained email, plus a pending unverified account holding your address.
Registering normally, or completing a password reset, takes the address over for login and
kills every outstanding link, though not the display name it was pre-registered under. See
the next entry. Nothing about it is worth acting on, but a support question about "why did I
get this" is a legitimate one and the answer is here.

**Reclaiming a pre-registered account through a resend or a reset keeps the name it was pre-
registered under.** `create_resend_url` takes `first_name`/`last_name` from the account row,
and a completed password reset never touches them either. Both confirm the address and let
the new owner set the account's password, but neither writes a name. If a stranger pre-
registered the address under a name of their choosing, that name is what `GET /auth/me`
returns afterwards, and what surfaces in project member lists and invitations, until the
account holder does one of two things: register the address again (which does write the
submitter's own names, the same as a free address) or edit the profile once signed in. Only
re-registering closes this in the same step that reclaims the credentials. A resend or a
reset does not.

**`POST /auth/register` still has a timing signal, of one bit and only once.** A submission whose email is
suppressed by the per-address budget skips an awaited round trip to the mail provider, so it
comes back measurably sooner than one that sends. A first probe can therefore learn that
mail was recently triggered for that address. It is weak and self- consuming: the probe is
itself a submission, so it spends from the same budget and changes the answer the next probe
gets, and it reports on recent activity rather than on whether an account exists: every
branch spends a slot, so no sequence of probes separates a free address from a taken one.
`POST /auth/resend-verification` has the narrower version of the same property: it awaits a
send only when the address has a pending signup, so a first probe against a clean budget
distinguishes that case. Closing either means making the send fire-and-forget, which is the
same queue change `forgot-password` needs for the identical property.

**A stranger who knows a pending address can use up its daily activation mail.** The budget is
per address and shared by every send the flow can trigger, which is what stops an inbox
being flooded. The cost is that anyone who knows an address with a signup already pending
can spend the day's five unauthenticated `resend-verification` calls against it, after which
the account holder's own resend, and their own re-registration, mail nothing while still
answering the usual `202`. Checking the password first cannot close it, because the check
would itself become the oracle the uniform response exists to remove. It opens nothing
further: any link mailed before the drain still works, and `forgot-password` draws on a
separate budget and now confirms the address on success, so a password reset gets the holder
in regardless. Support's answer to "I asked for the email again and nothing came" is to use
forgot password.

**A Redis outage lifts the per-address email caps.** `RedisEmailSendThrottle` answers `True`
on a `RedisError` (`api/auth/email_throttle.py`), so while the store is unreachable neither
the 60-second cooldown nor the five-a-day total applies to `forgot-password`, `register`, or
`resend-verification`, and someone rotating source addresses can put more mail in one inbox
than the cap allows. The fail-open predates deferred activation, and it exists for recovery:
a store hiccup must never be able to swallow a password-reset email. Deferred activation
widened its reach, since registration and resend now draw on the same throttle, so an outage
now lifts the cap on activation mail as well. Failing closed is the worse trade. These
endpoints answer the same `202` whether or not mail went out, so a closed throttle would
stop every signup and every reset silently for the duration. The acknowledgement would look
normal, nothing would arrive, and nothing would raise an error to alert on. The flood it
would prevent stays bounded meanwhile: the per-IP limiter survives a store outage by falling
back to slowapi's in-memory storage, which caps each source at `LIMIT_FALLBACK`, 60 requests
a minute per instance (looser than the 3 and 5 a minute those routes normally carry, so the
outage does widen this too). Redis is a hard requirement in every deployed profile, so an
outage here is short and is already paging someone. Handing the fallback to
`InMemoryEmailSendThrottle` instead came up and lost: it keeps a dict entry per address it
has seen and never evicts one, which would open a memory-growth path during exactly the
outage it was meant to cover.

**Login and refresh also return the refresh token in the JSON body.** The browser client
never reads it, since it uses the `HttpOnly` cookie, but programmatic clients can only
obtain the token this way, and `POST /auth/refresh` accepts it in the request body for
exactly that reason. Reading the body value requires script execution on the origin, which
the CSP (`script-src 'self'`), the explicit CORS allow-list, and `SameSite=Strict` between
them prevent. Rotation with reuse detection then caps the value of a token that does leak.

## Database

How the PostgreSQL databases stay locked down. This layer sits under the application and has
its own runbooks.

### Roles and least privilege

Every environment's database answers to two roles, never one:

- **`become_app`** is the application runtime role behind `DATABASE_URL`. It is a plain login
role: `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, and `NOBYPASSRLS`. Its rights stop at
`SELECT/INSERT/UPDATE/DELETE` on the application tables plus `USAGE`/`SELECT` on their
sequences. It cannot run DDL, create objects in `public`, or read another role's data.
- **`postgres`** is the Railway-provisioned superuser, which only Alembic uses, and only for
schema changes through `MIGRATION_DATABASE_URL`. Railway hands out exactly one superuser, so
there is no separate `migrator` role. Keeping migrations on a distinct URL is what isolates
DDL from the runtime token, without the overhead of in-session `SET ROLE`.

`scripts/db/roles.sql` is the idempotent source of truth for this setup. Run it against an
environment as `postgres` to reconcile the grants, the default privileges that hand every
future Alembic-created table to `become_app`, the `REVOKE CREATE ON SCHEMA public FROM
PUBLIC` lockdown, a pinned `search_path` (`pg_catalog, public`, which closes CVE-2018-1058
for the exposed role), and the role-level
`statement_timeout`/`idle_in_transaction_session_timeout`/ `lock_timeout`. Passwords stay
out of the file: they live in Railway variables.

`api/db/engine.py` hardens the connection itself. It requires TLS on deployed databases
(`sslmode=require`), tags each connection with an `application_name`, and repeats the
per-session statement and idle-in-transaction timeouts client-side through libpq `options`,
so a single runaway query cannot monopolize the database.

### Network exposure

Production and staging databases answer only on Railway's private network
(`*.railway.internal`). Their public TCP proxies are gone, so a leaked password is no longer
the sole barrier between the internet and the data. The dev database is the one exception,
and even there the proxy normally stays closed. Someone opens it in the Railway dashboard
only for a specific hands-on operation and shut again afterwards. That toggle is the
project's substitute for an IP allowlist, which Railway's platform does not offer.

### Audit logging

Railway's managed Postgres permits `ALTER SYSTEM`, so each database turns on connection
auditing directly and reloads without a restart:

```sql
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';
ALTER SYSTEM SET log_statement = 'ddl';
ALTER SYSTEM SET log_min_duration_statement = '5000';
SELECT pg_reload_conf();
```

Postgres then records connections and disconnections, logs every DDL statement, since only
Alembic should ever originate a schema change and anything else here is a red flag, and
captures statements slower than five seconds. The output flows into the Railway service
logs. Finer read/write auditing would need the `pgaudit` extension, but that requires
`shared_preload_libraries`, which Railway's image does not expose. `log_statement = 'ddl'`
remains the workable substitute.

### Backups

Railway's managed backups require the Pro plan, so on the current (free) plan the Postgres
volumes are
**not** backed up automatically. Until that changes, take manual dumps with
`scripts/db/backup.sh`, which opens a temporary proxy, runs `pg_dump`, and removes the proxy
again:

```bash
./scripts/db/backup.sh prod      # writes backups/prod-<timestamp>.dump
```

Run it before risky migrations and on a regular cadence. The dumps contain user data, so
they stay out of the repo: `.gitignore` covers `backups/`.

**That proxy is public while it is up.** Railway's TCP proxy exposes the database on an
internet-reachable host and port, so for the length of the dump the only thing between the
production database and the internet is the `postgres` superuser password. The
private-network isolation described under "Network exposure" is not in force. The script
removes the proxy on every exit path, including failure, but a killed terminal or a crashed
shell can still leave one behind. Two habits follow: run it attended rather than from a
cron, and if it ever exits abnormally, check the service's TCP proxies in the Railway
dashboard and delete any that are still there.

Restore into any database with:

```bash
pg_restore --no-owner --no-privileges -d <target-url> backups/<dump>
```

Upgrading the prod service to the Railway Pro plan would replace this with scheduled backups
plus point-in-time recovery.

## Data integrity and migrations

Deleting a user must not silently destroy other people's work. Most child rows clear
themselves through `ON DELETE CASCADE` (memberships, opinions, sent and received
invitations, reset tokens, activation tokens). A project a user **admins** is shared work,
so `projects.admin_id` uses `ON DELETE RESTRICT`: the database refuses to orphan or silently
erase a shared project, which is why the erasure endpoint requires an explicit disposition
for each one (see [GDPR](#gdpr-export-and-erasure)). Schema changes ship as reversible
Alembic migrations run through the migration-only superuser URL, keeping DDL off the runtime
role.
