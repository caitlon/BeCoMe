"""Decide whether a registration email address is acceptable.

Two independent, domain-only checks combine into a single policy:

1. A disposable-email blocklist: a vendored, hand-maintained list of well-known
   throwaway-mail providers (``api/data/disposable_email_domains.txt``). It is
   loaded once into a frozenset and matched against the address's domain
   exactly, case-insensitively. Refresh the file by hand from the public
   "disposable-email-domains" dataset
   (https://github.com/disposable-email-domains/disposable-email-domains) --
   never download it at runtime or at build time.

2. An MX / A / AAAA reachability check via ``dns.asyncresolver``. This check
   fails open: a resolver timeout, SERVFAIL, or any other resolver error lets
   the address through. Only a definitive negative -- NXDOMAIN, or a confirmed
   absence of both MX and A/AAAA records -- rejects. This is deliberate and is
   the opposite of what a reader instinctively expects from a validation
   function: our resolver having a bad day must never block a real signup. A
   definitive verdict is cached per domain (see ``DomainVerdictCache``) since
   the same domains repeat heavily across registrations: an accept for the
   full positive TTL, a rejection for a shorter one, since a domain can gain an
   MX record within the hour. An inconclusive lookup is never cached, so a
   brief resolver outage cannot pass every domain seen during it for the rest
   of the day.

Neither check reads any database state: both rejection reasons depend solely
on the domain string, so neither can leak whether an account already exists
for the address.
"""

import enum
import logging
import threading
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable

import dns.asyncresolver
import dns.exception
import dns.resolver
import redis

from api.config import get_settings
from api.exceptions import DisposableEmailDomainError, UnresolvableEmailDomainError

logger = logging.getLogger("api.service.email_policy")

# api/services/email_policy.py -> parents[1] is the api/ package root.
_DISPOSABLE_DOMAINS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "disposable_email_domains.txt"
)

# Total time budget (seconds) for a single MX/A/AAAA lookup, retries included.
MX_LOOKUP_TIMEOUT_SECONDS = 2.0

# How long a resolved accepting verdict is trusted before it is looked up again.
DOMAIN_VERDICT_CACHE_TTL_SECONDS = 24 * 60 * 60

# How long a definitive rejection is trusted. Shorter than the positive TTL on
# purpose: DNS negative-caching conventions cap negative TTLs well below positive
# ones, since a domain can gain an MX record at any time -- a freshly registered
# company domain must not stay locked out for the rest of the day.
NEGATIVE_DOMAIN_VERDICT_CACHE_TTL_SECONDS = 30 * 60


@lru_cache
def _load_disposable_domains() -> frozenset[str]:
    """Load the vendored disposable-domain list into a lowercased frozenset.

    Blank lines and ``#`` comments are ignored. The file is read once per
    process and cached, since it never changes at runtime.

    :return: The blocklisted domains, already lowercased.
    """
    domains: set[str] = set()
    with _DISPOSABLE_DOMAINS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            domains.add(stripped.lower())
    return frozenset(domains)


def _extract_domain(email: str) -> str:
    """Return the lowercased domain part of an email address.

    :param email: A syntactically valid email address (already validated
        upstream by the request schema).
    :return: The domain, lowercased.
    """
    return email.rsplit("@", 1)[-1].lower()


@runtime_checkable
class DomainVerdictCache(Protocol):
    """Cache backend for a resolved domain's mail-acceptance verdict."""

    def get(self, domain: str) -> bool | None:
        """Return the cached verdict, or ``None`` if absent or expired.

        :param domain: The lowercased domain to look up.
        :return: The cached verdict, or ``None`` on a miss.
        """
        ...

    def set(self, domain: str, verdict: bool, ttl_seconds: int) -> None:
        """Store a verdict for ``domain`` for ``ttl_seconds``.

        :param domain: The lowercased domain the verdict applies to.
        :param verdict: Whether the domain can plausibly receive mail.
        :param ttl_seconds: Time to live in seconds.
        """
        ...


class InMemoryDomainVerdictCache:
    """Process-local DomainVerdictCache for dev and tests (not shared across replicas)."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[bool, datetime]] = {}
        self._lock = threading.Lock()

    def get(self, domain: str) -> bool | None:
        """Return the cached verdict, or ``None`` if absent or expired.

        :param domain: The lowercased domain to look up.
        :return: The cached verdict, or ``None`` on a miss.
        """
        with self._lock:
            entry = self._entries.get(domain)
            if entry is None:
                return None
            verdict, expires_at = entry
            if expires_at <= datetime.now(UTC):
                del self._entries[domain]
                return None
            return verdict

    def set(self, domain: str, verdict: bool, ttl_seconds: int) -> None:
        """Store a verdict for ``domain`` for ``ttl_seconds``.

        A non-positive TTL is not stored (the entry would expire immediately),
        keeping behaviour identical to ``RedisDomainVerdictCache``.

        :param domain: The lowercased domain the verdict applies to.
        :param verdict: Whether the domain can plausibly receive mail.
        :param ttl_seconds: Time to live in seconds; values below 1 are not stored.
        """
        if ttl_seconds < 1:
            return
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        with self._lock:
            self._entries[domain] = (verdict, expires_at)


class RedisDomainVerdictCache:
    """Redis-backed DomainVerdictCache shared across replicas.

    Fail-open: a ``redis.RedisError`` is logged and swallowed. A read error is
    treated as a cache miss (the caller resolves the domain fresh), and a write
    error just means the verdict is not cached this time -- neither ever blocks
    or wrongly rejects a registration.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    @staticmethod
    def _key(domain: str) -> str:
        return f"email_policy:mx_verdict:{domain}"

    def get(self, domain: str) -> bool | None:
        """Return the cached verdict, or ``None`` on miss/error/corruption.

        :param domain: The lowercased domain to look up.
        :return: The cached verdict, or ``None`` on a miss.
        """
        try:
            raw = self._client.get(self._key(domain))
        except redis.RedisError:
            logger.warning(
                "email policy cache read failed",
                exc_info=True,
                extra={"event": "email_policy_cache_error", "op": "get", "domain": domain},
            )
            return None
        if raw is None:
            return None
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        if text == "1":
            return True
        if text == "0":
            return False
        return None

    def set(self, domain: str, verdict: bool, ttl_seconds: int) -> None:
        """Store a verdict for ``domain`` for ``ttl_seconds``; no-op on error.

        :param domain: The lowercased domain the verdict applies to.
        :param verdict: Whether the domain can plausibly receive mail.
        :param ttl_seconds: Time to live in seconds; values below 1 are not stored.
        """
        if ttl_seconds < 1:
            return
        try:
            self._client.set(self._key(domain), "1" if verdict else "0", ex=ttl_seconds)
        except redis.RedisError:
            logger.warning(
                "email policy cache write failed",
                exc_info=True,
                extra={"event": "email_policy_cache_error", "op": "set", "domain": domain},
            )


@lru_cache
def get_domain_verdict_cache() -> DomainVerdictCache:
    """Return the process-wide domain-verdict cache, Redis-backed when configured.

    :return: The process-wide domain verdict cache.
    """
    settings = get_settings()
    if settings.redis_url:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        return RedisDomainVerdictCache(client)
    return InMemoryDomainVerdictCache()


class _LookupOutcome(enum.Enum):
    """Classification of a single DNS record-type lookup."""

    FOUND = enum.auto()
    ABSENT = enum.auto()  # NoAnswer: the domain exists but has no record of this type
    DOMAIN_MISSING = enum.auto()  # NXDOMAIN: the domain does not exist at all
    INCONCLUSIVE = enum.auto()  # timeout, SERVFAIL, or any other resolver error


class EmailAddressPolicy:
    """Decide whether an email address is acceptable for registration.

    Combines two independent, domain-only checks -- a disposable-domain
    blocklist and an MX/A/AAAA reachability check -- behind a single entry
    point, :meth:`check`. Neither check reads database state, so neither can
    leak whether an account already exists for the address.
    """

    def __init__(
        self,
        *,
        disposable_domains: frozenset[str] | None = None,
        resolver: dns.asyncresolver.Resolver | None = None,
        cache: DomainVerdictCache | None = None,
        disposable_check_enabled: bool = True,
        mx_check_enabled: bool = True,
        timeout_seconds: float = MX_LOOKUP_TIMEOUT_SECONDS,
        cache_ttl_seconds: int = DOMAIN_VERDICT_CACHE_TTL_SECONDS,
        negative_cache_ttl_seconds: int = NEGATIVE_DOMAIN_VERDICT_CACHE_TTL_SECONDS,
    ) -> None:
        """Build the policy, wiring production defaults for anything not injected.

        :param disposable_domains: Blocklist to match against; defaults to the
            vendored list.
        :param resolver: DNS resolver used for the MX/A/AAAA check; when omitted
            a ``dns.asyncresolver.Resolver`` is built on first use, not here.
        :param cache: Domain-verdict cache; defaults to the process-wide cache
            (Redis-backed when configured, in-memory otherwise).
        :param disposable_check_enabled: Kill switch for the blocklist check.
        :param mx_check_enabled: Kill switch for the MX/A/AAAA check.
        :param timeout_seconds: Per-lookup DNS timeout budget, in seconds.
        :param cache_ttl_seconds: How long a confirmed-accepting verdict is
            cached, in seconds.
        :param negative_cache_ttl_seconds: How long a definitive rejection is
            cached, in seconds. Shorter than ``cache_ttl_seconds`` since a
            domain can gain an MX record at any time.
        """
        self._disposable_domains = (
            disposable_domains if disposable_domains is not None else _load_disposable_domains()
        )
        # Deliberately not built here. dns.asyncresolver.Resolver() reads the host's
        # resolver configuration and raises NoResolverConfiguration when it finds
        # none, so building it in __init__ turns every POST /register into a 500 --
        # and MX_CHECK_ENABLED=false, the switch that exists for exactly that
        # emergency, could not rescue it, because the object was built whether or not
        # the check ran. Built on first lookup instead, which the switch can prevent.
        self._resolver = resolver
        self._cache = cache if cache is not None else get_domain_verdict_cache()
        self._disposable_check_enabled = disposable_check_enabled
        self._mx_check_enabled = mx_check_enabled
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._negative_cache_ttl_seconds = negative_cache_ttl_seconds

    async def check(self, email: str) -> None:
        """Raise if the address is unacceptable for registration.

        :param email: A syntactically valid email address.
        :raises DisposableEmailDomainError: If the domain is a known disposable
            provider.
        :raises UnresolvableEmailDomainError: If the domain has no mail-capable
            DNS records.
        """
        domain = _extract_domain(email)
        if self._disposable_check_enabled and domain in self._disposable_domains:
            logger.info(
                "email policy rejected a disposable domain",
                extra={"event": "email_policy_rejected", "reason": "disposable", "domain": domain},
            )
            raise DisposableEmailDomainError(f"disposable email domain: {domain}")
        if self._mx_check_enabled and not await self._domain_accepts_mail(domain):
            logger.info(
                "email policy rejected an unresolvable domain",
                extra={
                    "event": "email_policy_rejected",
                    "reason": "unresolvable",
                    "domain": domain,
                },
            )
            raise UnresolvableEmailDomainError(f"domain has no mail-capable DNS records: {domain}")

    async def _domain_accepts_mail(self, domain: str) -> bool:
        """Return the cached verdict for ``domain``, resolving it on a cache miss.

        A definitive verdict (accept or reject) is cached; an inconclusive
        lookup is not cached at all, so a transient resolver fault does not
        pin that domain's verdict for the rest of the TTL window.

        :param domain: The lowercased domain to check.
        :return: Whether the domain can plausibly receive mail.
        """
        cached = self._cache.get(domain)
        if cached is not None:
            return cached

        outcome = await self._resolve_domain(domain)
        if outcome is _LookupOutcome.INCONCLUSIVE:
            logger.warning(
                "email policy DNS lookup was inconclusive, failing open",
                extra={"event": "email_policy_fail_open", "domain": domain},
            )
            return True

        verdict = outcome is _LookupOutcome.FOUND
        ttl = self._cache_ttl_seconds if verdict else self._negative_cache_ttl_seconds
        self._cache.set(domain, verdict, ttl)
        return verdict

    async def _resolve_domain(self, domain: str) -> _LookupOutcome:
        """Resolve whether ``domain`` can plausibly receive mail.

        Fails open: only a definitive negative rejects. See the module docstring.

        :param domain: The lowercased domain to resolve.
        :return: ``FOUND`` if some record accepts mail, ``DOMAIN_MISSING`` if the
            domain itself does not exist or MX, A, and AAAA are all confirmed
            absent, or ``INCONCLUSIVE`` if the resolver never gave a definitive
            answer.
        """
        mx_result = await self._lookup(domain, "MX")
        if mx_result is _LookupOutcome.FOUND:
            return _LookupOutcome.FOUND
        if mx_result is _LookupOutcome.DOMAIN_MISSING:
            return _LookupOutcome.DOMAIN_MISSING
        if mx_result is _LookupOutcome.INCONCLUSIVE:
            return _LookupOutcome.INCONCLUSIVE

        # mx_result is ABSENT: the domain exists but carries no MX record. Some
        # domains still receive mail straight to their A/AAAA address, so check
        # those before rejecting.
        for rdtype in ("A", "AAAA"):
            record_result = await self._lookup(domain, rdtype)
            if record_result is _LookupOutcome.FOUND:
                return _LookupOutcome.FOUND
            if record_result is _LookupOutcome.INCONCLUSIVE:
                return _LookupOutcome.INCONCLUSIVE

        # Confirmed absence of MX, A, and AAAA records for an existing domain.
        return _LookupOutcome.DOMAIN_MISSING

    def _get_resolver(self) -> dns.asyncresolver.Resolver:
        """Return the DNS resolver, building it on first use.

        A second builder racing this one would only construct a resolver that is
        immediately discarded, so no locking is needed: the whole method runs on the
        event loop with no ``await`` between the check and the assignment.

        :return: The resolver used for MX/A/AAAA lookups.
        :raises dns.resolver.NoResolverConfiguration: If the host has no usable
            resolver configuration. Reaching this means the MX check is switched on;
            turn ``MX_CHECK_ENABLED`` off and no lookup is attempted at all.
        """
        if self._resolver is None:
            self._resolver = dns.asyncresolver.Resolver()
        return self._resolver

    async def _lookup(self, domain: str, rdtype: str) -> _LookupOutcome:
        """Run one DNS query and classify the result.

        :param domain: The domain to query.
        :param rdtype: The DNS record type to query ("MX", "A", or "AAAA").
        :return: The classified outcome.
        """
        try:
            await self._get_resolver().resolve(domain, rdtype, lifetime=self._timeout_seconds)
        except dns.resolver.NXDOMAIN:
            return _LookupOutcome.DOMAIN_MISSING
        except dns.resolver.NoAnswer:
            return _LookupOutcome.ABSENT
        except dns.exception.DNSException:
            # Timeout, SERVFAIL (NoNameservers), or any other resolver-side fault.
            return _LookupOutcome.INCONCLUSIVE
        return _LookupOutcome.FOUND
