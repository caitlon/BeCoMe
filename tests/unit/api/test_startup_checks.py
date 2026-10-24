"""Tests for the checks of the application's backends made when the process starts."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis

from api import startup_checks
from api.config import get_settings

_LOGGER = "api.startup_checks"
_REDIS_URL = "redis://:leaked-password@secret-host.internal:6379/0"  # pragma: allowlist secret


def _settings(**update):
    return get_settings().model_copy(update=update)


def _records(caplog, level: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == _LOGGER and r.levelno == level]


@pytest.fixture
def client(monkeypatch):
    """A Redis client that answers PING; ``from_url`` records the URL and the timeouts."""
    fake = MagicMock()
    fake.ping = AsyncMock()
    fake.aclose = AsyncMock()
    from_url = MagicMock(return_value=fake)
    monkeypatch.setattr(startup_checks.aioredis, "from_url", from_url)
    fake.from_url = from_url
    return fake


@pytest.mark.asyncio
class TestRedis:
    async def test_pings_with_short_timeouts_and_closes_the_client(self, client, caplog):
        """
        GIVEN a Redis URL and a server that answers
        WHEN the Redis check runs
        THEN it pinged once with the 2 s timeouts the app's other clients use, closed the
             client, and logged one INFO record and no ERROR
        """
        # GIVEN
        caplog.set_level(logging.INFO, logger=_LOGGER)

        # WHEN
        await startup_checks.check_redis(_settings(redis_url=_REDIS_URL))

        # THEN
        client.from_url.assert_called_once_with(
            _REDIS_URL, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping.assert_awaited_once_with()
        client.aclose.assert_awaited_once_with()
        assert _records(caplog, logging.ERROR) == []
        (info,) = _records(caplog, logging.INFO)
        assert info.event == "redis_checked"

    @pytest.mark.parametrize(
        "error",
        [
            redis.AuthenticationError(f"wrong password for {_REDIS_URL}"),
            redis.ConnectionError(f"cannot reach {_REDIS_URL}"),
            redis.TimeoutError("slow"),
            RuntimeError("anything else"),
        ],
        ids=lambda e: type(e).__name__,
    )
    async def test_logs_one_error_with_the_class_only(self, client, caplog, error):
        """
        GIVEN a Redis that refuses the password, cannot be reached, is slow, or fails otherwise
        WHEN the Redis check runs
        THEN one ERROR carries the event, the class name as reason and none of the error's text,
             and the client is closed
        """
        # GIVEN
        client.ping.side_effect = error

        # WHEN
        await startup_checks.check_redis(_settings(redis_url=_REDIS_URL))

        # THEN
        (record,) = _records(caplog, logging.ERROR)
        assert record.event == "redis_check_failed"
        assert record.reason == type(error).__name__
        assert record.getMessage() == "Redis check failed at startup"
        assert "secret-host" not in " ".join(str(v) for v in vars(record).values())
        assert "leaked-password" not in " ".join(str(v) for v in vars(record).values())
        assert _records(caplog, logging.INFO) == []
        client.aclose.assert_awaited_once_with()

    async def test_a_cancelled_check_reaches_the_ping_and_still_closes_the_client(self, client):
        """
        GIVEN a Redis that never answers PING
        WHEN the task running the check is cancelled, as the lifespan does at shutdown
        THEN the cancellation ended the wait inside the ping, and the client was closed
        """
        # GIVEN
        pinging = asyncio.Event()

        async def ping():
            pinging.set()
            await asyncio.sleep(60)

        client.ping.side_effect = ping
        task = asyncio.create_task(startup_checks.check_redis(_settings(redis_url=_REDIS_URL)))
        await pinging.wait()

        # WHEN
        task.cancel()

        # THEN
        with pytest.raises(asyncio.CancelledError):
            await task
        client.aclose.assert_awaited_once_with()

    async def test_does_nothing_without_a_url(self, client, caplog):
        """
        GIVEN no Redis URL
        WHEN the Redis check runs
        THEN no client is built and nothing is logged
        """
        # GIVEN
        caplog.set_level(logging.INFO, logger=_LOGGER)

        # WHEN
        await startup_checks.check_redis(_settings(redis_url=""))

        # THEN
        client.from_url.assert_not_called()
        assert [r for r in caplog.records if r.name == _LOGGER] == []

    async def test_a_client_that_cannot_be_built_is_a_failed_check(self, monkeypatch, caplog):
        """
        GIVEN a URL the Redis library refuses to parse
        WHEN the Redis check runs
        THEN it is one ERROR with the class name, not an exception
        """
        # GIVEN
        monkeypatch.setattr(startup_checks.aioredis, "from_url", MagicMock(side_effect=ValueError))

        # WHEN
        await startup_checks.check_redis(_settings(redis_url="nonsense"))

        # THEN
        (record,) = _records(caplog, logging.ERROR)
        assert record.reason == "ValueError"


@pytest.mark.asyncio
class TestRunStartupChecks:
    async def test_checks_redis_and_skips_the_assistant_when_it_is_off(self, monkeypatch):
        """
        GIVEN the assistant switched off
        WHEN the startup checks run
        THEN Redis is checked and the assistant's module is never imported
        """
        # GIVEN
        checked = []

        async def check_redis(settings):
            checked.append("redis")

        monkeypatch.setattr(startup_checks, "check_redis", check_redis)
        monkeypatch.delitem(__import__("sys").modules, "api.assistant.startup", raising=False)

        # WHEN
        await startup_checks.run_startup_checks(_settings(assistant_enabled=False))

        # THEN
        assert checked == ["redis"]
        assert "api.assistant.startup" not in __import__("sys").modules

    async def test_checks_the_assistant_too_when_it_is_on(self, monkeypatch):
        """
        GIVEN the assistant switched on
        WHEN the startup checks run
        THEN both Redis and the assistant's backends are checked, with the same settings
        """
        # GIVEN
        from api.assistant import startup

        calls = []

        async def check_redis(settings):
            calls.append(("redis", settings))

        async def check_assistant_backends(settings):
            calls.append(("assistant", settings))

        monkeypatch.setattr(startup_checks, "check_redis", check_redis)
        monkeypatch.setattr(startup, "check_assistant_backends", check_assistant_backends)
        settings = _settings(assistant_enabled=True)

        # WHEN
        await startup_checks.run_startup_checks(settings)

        # THEN
        assert calls == [("redis", settings), ("assistant", settings)]

    async def test_a_failing_redis_check_does_not_stop_the_assistant_check(
        self, monkeypatch, caplog
    ):
        """
        GIVEN a Redis check that raises something unforeseen
        WHEN the startup checks run
        THEN nothing is raised, one ERROR names the class, and the assistant's check still ran
        """
        # GIVEN
        from api.assistant import startup

        ran = []

        async def check_redis(settings):
            raise RuntimeError("secret-host")

        async def check_assistant_backends(settings):
            ran.append(True)

        monkeypatch.setattr(startup_checks, "check_redis", check_redis)
        monkeypatch.setattr(startup, "check_assistant_backends", check_assistant_backends)

        # WHEN
        await startup_checks.run_startup_checks(_settings(assistant_enabled=True))

        # THEN
        (record,) = _records(caplog, logging.ERROR)
        assert record.event == "startup_checks_crashed"
        assert record.reason == "RuntimeError"
        assert "secret-host" not in " ".join(str(v) for v in vars(record).values())
        assert ran == [True]
