"""Shared, bounded pagination for list endpoints.

List endpoints accept an optional ``limit``/``offset`` and always cap ``limit`` at
``MAX_PAGE_SIZE`` so a single request can never pull an unbounded result set. The
parameters are additive and default to the first full page, so existing clients that
send neither keep working.
"""

from typing import Annotated

from fastapi import Query

# Hard ceiling on how many rows one list request may return, so an endpoint can never
# be driven to materialize an unbounded result set.
MAX_PAGE_SIZE = 100

# Largest accepted offset: far beyond any real page, and small enough to stay inside
# the database's integer range.
MAX_OFFSET = 2**31 - 1


class PaginationParams:
    """Bounded ``limit``/``offset`` query parameters shared by list endpoints.

    ``limit`` is clamped to ``MAX_PAGE_SIZE`` rather than rejected, so an oversized
    request still succeeds with a capped page instead of a 422. ``offset`` is bounded
    by ``MAX_OFFSET`` and a larger value is rejected with a 422. Both parameters are
    optional and default to the first full page.
    """

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, description="Maximum items to return")] = MAX_PAGE_SIZE,
        offset: Annotated[
            int, Query(ge=0, le=MAX_OFFSET, description="Number of items to skip")
        ] = 0,
    ) -> None:
        self.limit = min(limit, MAX_PAGE_SIZE)
        self.offset = offset
