"""Tests for the shared bounded pagination dependency."""

from api.pagination import MAX_PAGE_SIZE, PaginationParams


class TestPaginationParams:
    """PaginationParams defaults to the first full page and caps the page size."""

    def test_defaults_to_first_full_page(self):
        params = PaginationParams()
        assert params.limit == MAX_PAGE_SIZE
        assert params.offset == 0

    def test_clamps_oversized_limit_to_max(self):
        params = PaginationParams(limit=MAX_PAGE_SIZE * 10)
        assert params.limit == MAX_PAGE_SIZE

    def test_keeps_a_limit_below_the_cap(self):
        params = PaginationParams(limit=5, offset=20)
        assert params.limit == 5
        assert params.offset == 20
