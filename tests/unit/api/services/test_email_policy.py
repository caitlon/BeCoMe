"""Unit tests for the email address acceptance policy.

No test performs real DNS I/O: the resolver is always an injected mock.
"""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import dns.exception
import dns.resolver
import pytest
import redis

from api.exceptions import DisposableEmailDomainError, UnresolvableEmailDomainError
from api.services.email_policy import (
    DOMAIN_VERDICT_CACHE_TTL_SECONDS,
    MX_LOOKUP_TIMEOUT_SECONDS,
    DomainVerdictCache,
    EmailAddressPolicy,
    InMemoryDomainVerdictCache,
    RedisDomainVerdictCache,
    _extract_domain,
    _load_disposable_domains,
    get_domain_verdict_cache,
)
from tests.unit.api.conftest import mock_datetime_offset

_BLOCKED_DOMAINS = frozenset({"mailinator.com", "10minutemail.com"})


def _resolver(side_effect: object = None) -> MagicMock:
    """Build a resolver stub whose ``resolve`` is an AsyncMock.

    :param side_effect: Forwarded to the AsyncMock; a list cycles through
        results/exceptions per call, a single exception always raises, and
        ``None`` makes every call succeed with a throwaway Answer stand-in.
    """
    stub = MagicMock()
    if side_effect is not None:
        stub.resolve = AsyncMock(side_effect=side_effect)
    else:
        stub.resolve = AsyncMock(return_value=MagicMock())
    return stub


def _policy(
    resolver: MagicMock,
    *,
    disposable_check_enabled: bool = True,
    mx_check_enabled: bool = True,
) -> EmailAddressPolicy:
    """Build a policy wired with an isolated in-memory cache and given resolver."""
    return EmailAddressPolicy(
        resolver=resolver,
        cache=InMemoryDomainVerdictCache(),
        disposable_domains=_BLOCKED_DOMAINS,
        disposable_check_enabled=disposable_check_enabled,
        mx_check_enabled=mx_check_enabled,
    )


class TestDisposableBlocklist:
    """Tests for the disposable-domain blocklist check."""

    def test_blocklisted_domain_is_rejected(self):
        """
        GIVEN a domain on the disposable blocklist
        WHEN check() runs
        THEN DisposableEmailDomainError is raised
        """
        # GIVEN
        policy = _policy(_resolver())

        # WHEN / THEN
        with pytest.raises(DisposableEmailDomainError):
            asyncio.run(policy.check("user@mailinator.com"))

    def test_blocklist_check_is_case_insensitive(self):
        """
        GIVEN a blocklisted domain typed in mixed case
        WHEN check() runs
        THEN it is still rejected
        """
        # GIVEN
        policy = _policy(_resolver())

        # WHEN / THEN
        with pytest.raises(DisposableEmailDomainError):
            asyncio.run(policy.check("user@MailInator.COM"))

    def test_blocklisted_domain_does_not_reach_the_resolver(self):
        """
        GIVEN a blocklisted domain
        WHEN check() runs
        THEN the DNS resolver is never consulted (the cheap check short-circuits)
        """
        # GIVEN
        resolver = _resolver()
        policy = _policy(resolver)

        # WHEN
        with pytest.raises(DisposableEmailDomainError):
            asyncio.run(policy.check("user@mailinator.com"))

        # THEN
        resolver.resolve.assert_not_awaited()

    def test_normal_domain_passes_blocklist(self):
        """
        GIVEN a domain absent from the blocklist
        WHEN check() runs
        THEN no blocklist error is raised
        """
        # GIVEN
        policy = _policy(_resolver())

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@example.com"))

    def test_disposable_kill_switch_disables_the_check(self):
        """
        GIVEN the blocklist kill switch turned off
        WHEN check() runs for an otherwise-blocklisted domain
        THEN no error is raised
        """
        # GIVEN
        policy = _policy(_resolver(), disposable_check_enabled=False)

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@mailinator.com"))


class TestMxCheck:
    """Tests for the MX / A / AAAA reachability check."""

    def test_domain_with_mx_records_passes(self):
        """
        GIVEN a domain whose MX query succeeds
        WHEN check() runs
        THEN no error is raised and only the MX query is made
        """
        # GIVEN
        resolver = _resolver()
        policy = _policy(resolver)

        # WHEN
        asyncio.run(policy.check("user@example.com"))

        # THEN
        resolver.resolve.assert_awaited_once_with(
            "example.com", "MX", lifetime=MX_LOOKUP_TIMEOUT_SECONDS
        )

    def test_domain_with_no_mx_but_with_a_record_passes(self):
        """
        GIVEN a domain with no MX record but a valid A record
        WHEN check() runs
        THEN no error is raised
        """
        # GIVEN
        resolver = _resolver(side_effect=[dns.resolver.NoAnswer(), MagicMock()])
        policy = _policy(resolver)

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@example.com"))
        assert resolver.resolve.await_count == 2

    def test_domain_with_no_mx_no_a_but_aaaa_passes(self):
        """
        GIVEN a domain with only an AAAA record
        WHEN check() runs
        THEN no error is raised
        """
        # GIVEN
        resolver = _resolver(
            side_effect=[dns.resolver.NoAnswer(), dns.resolver.NoAnswer(), MagicMock()]
        )
        policy = _policy(resolver)

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@example.com"))
        assert resolver.resolve.await_count == 3

    def test_nxdomain_is_rejected(self):
        """
        GIVEN a domain that does not exist (NXDOMAIN)
        WHEN check() runs
        THEN UnresolvableEmailDomainError is raised
        """
        # GIVEN
        policy = _policy(_resolver(side_effect=dns.resolver.NXDOMAIN()))

        # WHEN / THEN
        with pytest.raises(UnresolvableEmailDomainError):
            asyncio.run(policy.check("user@doesnotexist.invalid"))

    def test_confirmed_absence_of_mx_a_and_aaaa_is_rejected(self):
        """
        GIVEN a domain that exists but carries no MX, A, or AAAA records
        WHEN check() runs
        THEN UnresolvableEmailDomainError is raised
        """
        # GIVEN
        resolver = _resolver(
            side_effect=[
                dns.resolver.NoAnswer(),
                dns.resolver.NoAnswer(),
                dns.resolver.NoAnswer(),
            ]
        )
        policy = _policy(resolver)

        # WHEN / THEN
        with pytest.raises(UnresolvableEmailDomainError):
            asyncio.run(policy.check("user@example.com"))

    def test_resolver_timeout_passes(self):
        """
        GIVEN the resolver times out
        WHEN check() runs
        THEN no error is raised

        This is the fail-open guarantee: our resolver having a bad day must
        never block a legitimate registration. It is the single most important
        test in this module.
        """
        # GIVEN
        policy = _policy(_resolver(side_effect=dns.exception.Timeout()))

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@example.com"))

    def test_timeout_does_not_fall_back_to_a_or_aaaa(self):
        """
        GIVEN the MX query times out
        WHEN check() runs
        THEN the address passes immediately without an A/AAAA fallback query
        """
        # GIVEN
        resolver = _resolver(side_effect=dns.exception.Timeout())
        policy = _policy(resolver)

        # WHEN
        asyncio.run(policy.check("user@example.com"))

        # THEN
        resolver.resolve.assert_awaited_once()

    def test_timeout_during_a_fallback_lookup_passes(self):
        """
        GIVEN no MX record and the A fallback query times out
        WHEN check() runs
        THEN no error is raised and AAAA is never queried
        """
        # GIVEN
        resolver = _resolver(side_effect=[dns.resolver.NoAnswer(), dns.exception.Timeout()])
        policy = _policy(resolver)

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@example.com"))
        assert resolver.resolve.await_count == 2

    def test_servfail_passes(self):
        """
        GIVEN the resolver reports SERVFAIL (all nameservers failed)
        WHEN check() runs
        THEN no error is raised
        """
        # GIVEN
        policy = _policy(_resolver(side_effect=dns.resolver.NoNameservers()))

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@example.com"))

    def test_generic_resolver_error_passes(self):
        """
        GIVEN an unenumerated dnspython error
        WHEN check() runs
        THEN no error is raised (fail open covers the whole DNSException family)
        """
        # GIVEN
        policy = _policy(_resolver(side_effect=dns.exception.DNSException("weird failure")))

        # WHEN / THEN (no raise)
        asyncio.run(policy.check("user@example.com"))

    def test_mx_kill_switch_disables_the_check(self):
        """
        GIVEN the MX-check kill switch turned off
        WHEN check() runs for a domain that would otherwise be rejected
        THEN no error is raised and the resolver is never consulted
        """
        # GIVEN
        resolver = _resolver(side_effect=dns.resolver.NXDOMAIN())
        policy = _policy(resolver, mx_check_enabled=False)

        # WHEN
        asyncio.run(policy.check("user@doesnotexist.invalid"))

        # THEN
        resolver.resolve.assert_not_awaited()


class TestDomainVerdictCaching:
    """Tests for the policy's use of the per-domain verdict cache."""

    def test_second_lookup_of_same_domain_hits_the_cache(self):
        """
        GIVEN two addresses sharing a domain
        WHEN check() runs for both
        THEN the resolver is consulted only once
        """
        # GIVEN
        resolver = _resolver()
        cache = InMemoryDomainVerdictCache()
        policy = EmailAddressPolicy(resolver=resolver, cache=cache, disposable_domains=frozenset())

        # WHEN
        asyncio.run(policy.check("first@example.com"))
        asyncio.run(policy.check("second@example.com"))

        # THEN
        resolver.resolve.assert_awaited_once()

    def test_cached_rejection_is_reused_without_a_second_lookup(self):
        """
        GIVEN a domain whose cached verdict is a rejection
        WHEN check() runs again for the same domain
        THEN it raises again without touching the resolver
        """
        # GIVEN
        resolver = _resolver(side_effect=dns.resolver.NXDOMAIN())
        cache = InMemoryDomainVerdictCache()
        policy = EmailAddressPolicy(resolver=resolver, cache=cache, disposable_domains=frozenset())
        with pytest.raises(UnresolvableEmailDomainError):
            asyncio.run(policy.check("first@example.com"))

        # WHEN / THEN
        with pytest.raises(UnresolvableEmailDomainError):
            asyncio.run(policy.check("second@example.com"))
        resolver.resolve.assert_awaited_once()


class TestExtractDomain:
    """Tests for the email-to-domain helper."""

    @pytest.mark.parametrize(
        ("email", "expected_domain"),
        [
            ("user@example.com", "example.com"),
            ("USER@EXAMPLE.COM", "example.com"),
            ("user@Sub.Example.COM", "sub.example.com"),
        ],
    )
    def test_extracts_lowercased_domain(self, email, expected_domain):
        """
        GIVEN an email address in varying case
        WHEN _extract_domain runs
        THEN it returns the lowercased domain
        """
        # GIVEN / WHEN / THEN
        assert _extract_domain(email) == expected_domain


class TestLoadDisposableDomains:
    """Tests for the vendored blocklist loader."""

    def test_parses_domains_ignoring_comments_blanks_and_case(self, tmp_path, monkeypatch):
        """
        GIVEN a domain file with comments, blank lines, and mixed case
        WHEN _load_disposable_domains runs
        THEN it returns only the lowercased domain lines
        """
        # GIVEN
        import api.services.email_policy as email_policy_module

        domains_file = tmp_path / "disposable.txt"
        domains_file.write_text(
            "# leading comment\n\nMailinator.COM\nexample.test\n   \n# another comment\nFoo.Bar\n"
        )
        monkeypatch.setattr(email_policy_module, "_DISPOSABLE_DOMAINS_PATH", domains_file)
        _load_disposable_domains.cache_clear()

        # WHEN
        domains = _load_disposable_domains()

        # THEN
        assert domains == frozenset({"mailinator.com", "example.test", "foo.bar"})

        # Cleanup: do not leak the patched path into later tests.
        _load_disposable_domains.cache_clear()

    def test_real_vendored_file_contains_well_known_providers(self):
        """
        GIVEN the real vendored blocklist file
        WHEN _load_disposable_domains runs
        THEN it contains the providers named in the task brief
        """
        # GIVEN / WHEN
        domains = _load_disposable_domains()

        # THEN
        for provider in (
            "mailinator.com",
            "10minutemail.com",
            "guerrillamail.com",
            "yopmail.com",
            "temp-mail.org",
            "throwawaymail.com",
            "getnada.com",
            "maildrop.cc",
            "dispostable.com",
            "sharklasers.com",
            "trashmail.com",
        ):
            assert provider in domains


class TestInMemoryDomainVerdictCache:
    """Tests for the in-memory domain-verdict cache."""

    def test_get_returns_none_on_miss(self):
        """
        GIVEN an empty cache
        WHEN get() is called
        THEN it returns None
        """
        # GIVEN
        cache = InMemoryDomainVerdictCache()

        # WHEN / THEN
        assert cache.get("example.com") is None

    def test_set_then_get_roundtrips_a_true_verdict(self):
        """
        GIVEN a cached True verdict
        WHEN get() is called
        THEN it returns True
        """
        # GIVEN
        cache = InMemoryDomainVerdictCache()

        # WHEN
        cache.set("example.com", True, ttl_seconds=60)

        # THEN
        assert cache.get("example.com") is True

    def test_set_then_get_roundtrips_a_false_verdict(self):
        """
        GIVEN a cached False verdict
        WHEN get() is called
        THEN it returns False, not None (a rejection must be distinguishable from a miss)
        """
        # GIVEN
        cache = InMemoryDomainVerdictCache()

        # WHEN
        cache.set("bad.example", False, ttl_seconds=60)

        # THEN
        assert cache.get("bad.example") is False

    def test_expired_entry_returns_none(self):
        """
        GIVEN an entry stored with a positive TTL that has since elapsed
        WHEN get() is called
        THEN it returns None and the stale entry is dropped

        Backdates the store so the TTL math itself expires the entry, rather
        than relying on set()'s non-positive-TTL guard (a different code path,
        covered separately by test_nonpositive_ttl_is_not_stored).
        """
        # GIVEN
        cache = InMemoryDomainVerdictCache()
        with mock_datetime_offset("api.services.email_policy.datetime", timedelta(hours=25)):
            cache.set("example.com", True, ttl_seconds=DOMAIN_VERDICT_CACHE_TTL_SECONDS)  # 24h

        # WHEN / THEN
        assert cache.get("example.com") is None

    def test_nonpositive_ttl_is_not_stored(self):
        """
        GIVEN a set() call with ttl_seconds=0
        WHEN get() is called
        THEN it returns None (never stored)
        """
        # GIVEN
        cache = InMemoryDomainVerdictCache()

        # WHEN
        cache.set("example.com", True, ttl_seconds=0)

        # THEN
        assert cache.get("example.com") is None

    def test_satisfies_protocol(self):
        """InMemoryDomainVerdictCache implements the DomainVerdictCache protocol."""
        assert isinstance(InMemoryDomainVerdictCache(), DomainVerdictCache)


class TestRedisDomainVerdictCache:
    """Tests for the Redis-backed domain-verdict cache."""

    def test_set_then_get_roundtrips_and_sets_a_ttl(self):
        """
        GIVEN a cached verdict
        WHEN get() is called
        THEN it returns the verdict and the key carries a positive TTL
        """
        # GIVEN
        import fakeredis

        client = fakeredis.FakeStrictRedis()
        cache = RedisDomainVerdictCache(client)

        # WHEN
        cache.set("example.com", True, ttl_seconds=60)

        # THEN
        assert cache.get("example.com") is True
        assert client.ttl(RedisDomainVerdictCache._key("example.com")) > 0

    def test_stores_a_false_verdict_distinctly_from_a_miss(self):
        """
        GIVEN a cached False verdict
        WHEN get() is called
        THEN it returns False, not None
        """
        # GIVEN
        import fakeredis

        client = fakeredis.FakeStrictRedis()
        cache = RedisDomainVerdictCache(client)

        # WHEN
        cache.set("bad.example", False, ttl_seconds=60)

        # THEN
        assert cache.get("bad.example") is False

    def test_nonpositive_ttl_is_not_stored(self):
        """
        GIVEN a set() call with ttl_seconds=0
        WHEN get() is called
        THEN it returns None (never stored)
        """
        # GIVEN
        import fakeredis

        client = fakeredis.FakeStrictRedis()
        cache = RedisDomainVerdictCache(client)

        # WHEN
        cache.set("example.com", True, ttl_seconds=0)

        # THEN
        assert cache.get("example.com") is None

    def test_is_fail_open_on_read_and_write_errors(self):
        """
        GIVEN a Redis client that always errors
        WHEN get()/set() are called
        THEN both are swallowed: get() returns None and set() does not raise
        """
        # GIVEN
        client = MagicMock()
        client.get.side_effect = redis.RedisError("down")
        client.set.side_effect = redis.RedisError("down")
        cache = RedisDomainVerdictCache(client)

        # WHEN / THEN
        assert cache.get("example.com") is None
        cache.set("example.com", True, ttl_seconds=60)  # must not raise

    def test_treats_a_corrupted_value_as_a_miss(self):
        """
        GIVEN a key holding a value that is neither "1" nor "0"
        WHEN get() is called
        THEN it returns None
        """
        # GIVEN
        import fakeredis

        client = fakeredis.FakeStrictRedis()
        client.set(RedisDomainVerdictCache._key("example.com"), b"garbage")
        cache = RedisDomainVerdictCache(client)

        # WHEN / THEN
        assert cache.get("example.com") is None

    def test_satisfies_protocol(self):
        """RedisDomainVerdictCache implements the DomainVerdictCache protocol."""
        import fakeredis

        assert isinstance(RedisDomainVerdictCache(fakeredis.FakeStrictRedis()), DomainVerdictCache)


class TestGetDomainVerdictCache:
    """Tests for the process-wide domain-verdict cache factory."""

    def test_returns_in_memory_when_redis_url_unset(self, monkeypatch):
        """
        GIVEN settings without a Redis URL
        WHEN get_domain_verdict_cache() is called
        THEN it returns an InMemoryDomainVerdictCache
        """
        # GIVEN
        from api.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("REDIS_URL", "")
        get_domain_verdict_cache.cache_clear()

        # WHEN
        cache = get_domain_verdict_cache()

        # THEN
        assert isinstance(cache, InMemoryDomainVerdictCache)

        # Cleanup
        get_domain_verdict_cache.cache_clear()
        get_settings.cache_clear()

    def test_returns_redis_backed_when_redis_url_set(self, monkeypatch):
        """
        GIVEN settings with a Redis URL configured
        WHEN get_domain_verdict_cache() is called
        THEN it returns a RedisDomainVerdictCache
        """
        # GIVEN
        from api.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        get_domain_verdict_cache.cache_clear()

        # WHEN
        cache = get_domain_verdict_cache()

        # THEN
        assert isinstance(cache, RedisDomainVerdictCache)

        # Cleanup
        get_domain_verdict_cache.cache_clear()
        get_settings.cache_clear()
        monkeypatch.undo()
        get_settings.cache_clear()

    def test_is_a_singleton(self):
        """
        GIVEN two calls to get_domain_verdict_cache()
        WHEN compared
        THEN they return the identical instance
        """
        # GIVEN
        get_domain_verdict_cache.cache_clear()

        # WHEN
        first = get_domain_verdict_cache()
        second = get_domain_verdict_cache()

        # THEN
        assert first is second

        # Cleanup
        get_domain_verdict_cache.cache_clear()
