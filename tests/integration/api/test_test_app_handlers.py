"""The integration test app answers errors the way the real app does.

``create_test_app()`` builds the integration tier's app by hand, and ``test_test_app_routes.py``
pins that its routes equal the real app's. Routes are only part of what a client sees: a 429, a
422 or a 500 comes from an exception handler, a middleware or an app-level dependency, and an
app that registers a different one answers differently from the real service while every
integration test stays green. The 429 was the case that showed it: the test app registered
slowapi's raw handler, so no test saw the ``rate_limit_exceeded`` log record or the
``Retry-After`` header clients get from ``rate_limit_handler``.

This compares what each app has, with the assistant switched on in both builds:

* The exception handlers must be the same objects under the same keys. There is no deliberate
  difference today, so any difference is a bug in ``create_test_app()``.
* The middleware may differ only where ``DELIBERATE_MIDDLEWARE_DIFFERENCES`` says so, each with
  the reason and the test that covers the behaviour instead.
* The real app has the default-limits dependency and the test app leaves it out on purpose.

The last test checks the behaviour the first one protects: the 429 the test app answers.
"""

import logging
from collections.abc import Iterable
from typing import cast
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from api.middleware.body_size import BodySizeLimitMiddleware
from api.middleware.origin_lock import OriginLockMiddleware
from api.middleware.rate_limit import (
    LIMIT_PWD_RESET,
    enforce_default_limits,
    limiter,
)
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.middleware.unhandled_errors import UnhandledErrorMiddleware
from tests.integration.api.conftest import create_test_app
from tests.unit.api.route_table import real_app

# Middleware the real app has and the test app leaves out, each with the reason and where the
# behaviour is tested instead. Adding an entry is a decision, not a formality: say where the
# behaviour is covered, and check that the file does cover it.
DELIBERATE_MIDDLEWARE_DIFFERENCES: dict[type, str] = {
    UnhandledErrorMiddleware: (
        "Without it an exception no handler maps reaches TestClient raised, with its traceback, "
        "so a broken integration test fails at the bug and not on an opaque 500. The 500 the "
        "middleware answers is tested in tests/unit/api/middleware/test_unhandled_errors.py."
    ),
    SecurityHeadersMiddleware: (
        "Response headers only; no integration test reads them. Tested in "
        "tests/unit/api/middleware/test_security_headers.py on a minimal app."
    ),
    BodySizeLimitMiddleware: (
        "Guards the request size, which no integration request approaches. Tested on the real "
        "app and on minimal apps in tests/unit/api/middleware/test_body_size.py."
    ),
    OriginLockMiddleware: (
        "Added only when settings.is_deploy, so the real build in this test does not add it "
        "either: it is listed so a deployed build is not mistaken for a gap. Tested on the real "
        "app under the deployed profiles in tests/unit/api/middleware/test_origin_lock.py."
    ),
    CORSMiddleware: (
        "Cross-origin headers and preflight; the test client sends no Origin. Tested on the "
        "real app in tests/unit/api/test_main.py (exposed and allowed headers), in "
        "tests/unit/api/middleware/test_origin_lock.py (a refusal keeps the CORS headers) and in "
        "tests/integration/api/middleware/test_request_logging_wiring.py (the preflight)."
    ),
}


def _middleware_classes(app: FastAPI) -> set[type]:
    """List the middleware classes an app was built with.

    :param app: The application to inspect.
    :return: The class of each entry of ``app.user_middleware``.
    """
    # ``cls`` is typed as a factory, but the entries are the classes handed to add_middleware.
    return {cast(type, middleware.cls) for middleware in app.user_middleware}


def _describe(handlers: Iterable[object]) -> list[str]:
    """Name handlers for a failure message.

    :param handlers: Handler callables (or ``None`` for a missing one).
    :return: ``module.qualname`` of each, in the same order.
    """
    return [
        f"{getattr(handler, '__module__', '?')}.{getattr(handler, '__qualname__', handler)}"
        for handler in handlers
    ]


def test_test_app_registers_the_exception_handlers_of_the_real_app(assistant_settings):
    """
    GIVEN the real app and the integration test app, both built with the assistant on
    WHEN their exception handlers are compared key by key
    THEN both have the same exception classes, each mapped to the very same handler
    """
    # GIVEN
    real = real_app().exception_handlers
    test_app = create_test_app().exception_handlers

    # WHEN
    keys = set(real) | set(test_app)
    different = sorted(
        (key for key in keys if real.get(key) is not test_app.get(key)), key=lambda k: k.__name__
    )

    # THEN
    assert any(
        getattr(key, "__module__", "").startswith("api.assistant") for key in real | test_app
    ), "no assistant exception handler in either app: the comparison ran with the flag off"
    assert not different, "exception handlers differ between the real app and the test app: " + (
        "; ".join(
            f"{key.__name__}: real={_describe([real.get(key)])[0]}, "
            f"test app={_describe([test_app.get(key)])[0]}"
            for key in different
        )
        + ". Register the real handler in create_test_app() in tests/integration/api/conftest.py."
    )


class TestMiddleware:
    """The test app carries the real app's middleware, bar the ones listed with a reason."""

    def test_test_app_has_no_middleware_the_real_app_lacks(self, assistant_settings):
        """
        GIVEN the real app and the integration test app
        WHEN their middleware classes are compared
        THEN the test app has nothing the real app lacks
        """
        # WHEN
        extra = _middleware_classes(create_test_app()) - _middleware_classes(real_app())

        # THEN
        assert not extra, (
            f"middleware only in the test app: {sorted(cls.__name__ for cls in extra)}. "
            "A request the integration tier makes would pass through code the service never runs."
        )

    def test_every_middleware_missing_from_the_test_app_is_listed_with_a_reason(
        self, assistant_settings
    ):
        """
        GIVEN the real app and the integration test app
        WHEN the middleware only the real app has is listed
        THEN each of them is a key of DELIBERATE_MIDDLEWARE_DIFFERENCES
        """
        # WHEN
        missing = _middleware_classes(real_app()) - _middleware_classes(create_test_app())
        unexplained = missing - DELIBERATE_MIDDLEWARE_DIFFERENCES.keys()

        # THEN
        assert not unexplained, (
            f"middleware only in the real app, without a reason: "
            f"{sorted(cls.__name__ for cls in unexplained)}. Add it to create_test_app() or "
            "to DELIBERATE_MIDDLEWARE_DIFFERENCES with the reason and the test that covers it."
        )

    def test_a_listed_difference_is_still_a_difference(self, assistant_settings):
        """
        GIVEN the middleware the test app deliberately leaves out
        WHEN the middleware of the test app is read
        THEN none of them is there, so no reason in the table is stale
        """
        # WHEN
        stale = _middleware_classes(create_test_app()) & DELIBERATE_MIDDLEWARE_DIFFERENCES.keys()

        # THEN
        assert not stale, (
            f"in DELIBERATE_MIDDLEWARE_DIFFERENCES but now in the test app: "
            f"{sorted(cls.__name__ for cls in stale)}. Remove the entry."
        )


def test_test_app_leaves_out_the_default_limits_the_real_app_enforces(assistant_settings):
    """
    GIVEN the real app and the integration test app
    WHEN their app-level dependencies are read
    THEN the real app counts the default limits and the test app does not, on purpose:
        the default limits are tested on the real app in test_default_rate_limits.py
    """
    # WHEN
    real = [dependency.dependency for dependency in real_app().router.dependencies]
    test_app = [dependency.dependency for dependency in create_test_app().router.dependencies]

    # THEN
    assert enforce_default_limits in real, "the real app no longer enforces the default limits"
    assert test_app == [], (
        f"the test app gained app-level dependencies: {_describe(test_app)}. "
        "Compare them with api/main.py::create_app() and update this test."
    )


class _RecordCollector(logging.Handler):
    """Keep the records of one logger, whether or not it propagates to the root."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_rate_limited_request_gets_the_429_of_the_real_handler(client: TestClient) -> None:
    """
    GIVEN a route limited to LIMIT_PWD_RESET and the limiter switched on
    WHEN the route is called once more than the limit allows
    THEN the last answer is 429 with an integer Retry-After within the window,
        and the rate_limit_exceeded record the real handler writes is logged
    """
    # GIVEN
    allowed = int(LIMIT_PWD_RESET.split("/")[0])
    window_seconds = 60
    body = {"email": "nobody@example.com"}
    # The api loggers stop propagating once any test configures logging, so caplog cannot be
    # relied on: the collector goes on the logger itself.
    ratelimit_logger = logging.getLogger("api.ratelimit")
    collector = _RecordCollector()
    ratelimit_logger.addHandler(collector)

    # WHEN
    try:
        with patch.object(limiter, "enabled", True):
            limiter.reset()
            try:
                answers = [
                    client.post("/api/v1/auth/forgot-password", json=body)
                    for _ in range(allowed + 1)
                ]
            finally:
                limiter.reset()
    finally:
        ratelimit_logger.removeHandler(collector)

    # THEN
    assert [answer.status_code for answer in answers] == [202] * allowed + [429]
    retry_after = answers[-1].headers["Retry-After"]
    assert retry_after.isdigit()
    assert 1 <= int(retry_after) <= window_seconds
    events = [getattr(record, "event", None) for record in collector.records]
    assert events == ["rate_limit_exceeded"]
