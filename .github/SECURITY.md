# Security policy

BeCoMe is a multi-tenant web application for group decision-making, live at
[becomify.app](https://www.becomify.app) and currently in beta. Each tenant's data is private:
the projects, the expert panels, and the opinions behind every decision. Anything that breaks
that isolation is a security bug, and this page says how to report one.

## Supported versions

Only the version currently deployed to becomify.app receives security fixes. The project is
pre-1.0, so there is no long-term support branch yet. Earlier tags are snapshots, and I do not
patch them.

| Version | Supported |
|---------|-----------|
| Latest release on becomify.app | Yes |
| Earlier pre-release tags | No |

## Reporting a vulnerability

Do not open a public issue for anything security-sensitive. Report it privately through
[GitHub Private Vulnerability Reporting](https://github.com/caitlon/BeCoMe/security/advisories/new),
which keeps the details between us until a fix ships.

Include a short proof of concept: the request, the steps, and the affected endpoint or page.
That is what lets me reproduce the problem. I will acknowledge your report within 72 hours.

## What happens next

Once I have acknowledged the report, I confirm the issue, gauge its impact, and work on a fix
that reaches production before any details go public. I will send you updates as the fix
progresses and credit you in the advisory when I publish it, unless you would rather stay
anonymous. A valid issue gets a patch in production within 30 days. Anything under active
exploitation moves faster.

## In scope

These parts of BeCoMe are the most worth probing:

- Authentication and session handling: JWT issuing, refresh, logout, and password reset
- Tenant isolation: reading or changing another tenant's projects, experts, or opinions
- Injection of any kind (SQL, command, stored or reflected XSS)
- Exposure of personal data or credentials, including secrets that leak into logs
- Bypassing the API rate limits or input validation

## Out of scope

- Volumetric denial of service or load testing against the live site
- Scanner output with no working proof of concept
- Missing security headers or best-practice notes with no demonstrated impact
- Social engineering, phishing, and physical access
- Flaws in third-party dependencies that BeCoMe never reaches. Report those upstream.

## Related documentation

[`docs/security.md`](../docs/security.md) covers the application security posture:
authentication and session transport, tenant isolation, rate limiting, GDPR handling, and the
database layer (least-privilege roles, network isolation, audit logging, and secret rotation).
Deployment topology and per-environment configuration live in
[`docs/environments.md`](../docs/environments.md).
