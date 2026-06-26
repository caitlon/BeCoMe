# Security Policy

BeCoMe is a multi-tenant web application for group decision-making, live at
[becomify.app](https://www.becomify.app) and currently in beta. Each tenant's data — its
projects, expert panels, and the opinions behind every decision — is private, so security
reports get serious attention.

## Supported Versions

Only the version currently deployed to becomify.app receives security fixes. The project is
pre-1.0, so there is no long-term support branch yet; earlier tags are snapshots and are not
patched.

| Version | Supported |
|---------|-----------|
| Latest release on becomify.app | Yes |
| Earlier pre-release tags | No |

## Reporting a Vulnerability

Please do not open a public issue for anything security-sensitive. Report it privately
through [GitHub Private Vulnerability Reporting](https://github.com/caitlon/BeCoMe/security/advisories/new),
which keeps the details between us until a fix ships.

A short proof of concept — the request, the steps, the affected endpoint or page — lets me
reproduce the problem quickly. I will acknowledge your report within 72 hours.

## What happens next

Once I have acknowledged the report, I confirm the issue, gauge its impact, and work on a fix
that reaches production before any details go public. I will keep you posted as that moves
along and credit you in the advisory when it is published, unless you would rather stay
anonymous. A valid issue should have a patch deployed within 30 days; anything under active
exploitation moves faster.

## In scope

The parts of BeCoMe most worth probing:

- Authentication and session handling: JWT issuing, refresh, logout, and password reset
- Tenant isolation — reading or changing another tenant's projects, experts, or opinions
- Injection of any kind (SQL, command, stored or reflected XSS)
- Exposure of personal data or credentials, including secrets that leak into logs
- Bypassing the API rate limits or input validation

## Out of scope

- Volumetric denial of service or load testing against the live site
- Scanner output with no working proof of concept
- Missing security headers or best-practice notes with no demonstrated impact
- Social engineering, phishing, and physical access
- Flaws in third-party dependencies that BeCoMe never actually reaches — report those upstream

## Related documentation

The database security posture — least-privilege roles, network isolation, audit logging, and
secret rotation — is written up in [`docs/security.md`](../docs/security.md). Deployment
topology and per-environment configuration live in
[`docs/environments.md`](../docs/environments.md).
