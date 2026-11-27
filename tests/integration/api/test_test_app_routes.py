"""The integration test app serves the same routes as the real app.

The sweeps in ``routes/test_anonymous_access.py`` and ``routes/test_cross_tenant_access.py``
walk ``create_test_app()``, which includes the routers by hand. A router added to
``create_app()`` and left out of ``create_test_app()`` would never receive an anonymous or a
cross-tenant request, and nothing would say so. This compares the two route sets, with the
assistant switched on in both.

Only the assistant router is conditional in both builds, so the comparison runs with the flag on.
The flag-off route sets are not compared with each other; ``test_assistant_config.py`` checks
only that the flag-off test app serves no assistant route.
"""

from collections.abc import Iterable

from tests.integration.api.conftest import create_test_app
from tests.unit.api.route_table import app_routes, iter_api_routes

ASSISTANT_PREFIX = "/api/v1/assistant"


def _method_path_pairs(routes: Iterable[object]) -> set[tuple[str, str]]:
    """List the ``(method, path template)`` pairs of a route list.

    :param routes: An app's ``routes``.
    :return: One pair per method of each ``APIRoute``.
    """
    return {
        (method, route.path) for route in iter_api_routes(routes) for method in route.methods or ()
    }


def test_test_app_serves_the_routes_of_the_real_app(assistant_settings):
    """
    GIVEN the real app and the integration test app, both built with the assistant on
    WHEN the (method, path) pairs of each are listed
    THEN the two sets are equal, and the assistant routes are among them
    """
    # WHEN
    real = _method_path_pairs(app_routes())
    test_app = _method_path_pairs(create_test_app().routes)

    # THEN
    assert any(path.startswith(ASSISTANT_PREFIX) for _, path in real | test_app), (
        "no assistant route in either app: the comparison ran with the flag off"
    )
    assert real == test_app, (
        f"routes only in the real app: {sorted(real - test_app)}; "
        f"routes only in the test app: {sorted(test_app - real)}. "
        "Include the router in create_test_app() in tests/integration/api/conftest.py."
    )
