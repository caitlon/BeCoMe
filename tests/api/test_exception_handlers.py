"""Tests for exception handlers."""

from fastapi import status

from api.exceptions import BeCoMeAPIError, NotFoundError, ValidationError
from api.middleware.exception_handlers import _get_status_and_detail


class TestGetStatusAndDetail:
    """Tests for _get_status_and_detail function."""

    def test_unknown_not_found_error_uses_base_class_mapping(self):
        """
        GIVEN a NotFoundError subclass not in EXCEPTION_MAP
        WHEN _get_status_and_detail is called
        THEN it falls back to NotFoundError base class mapping
        """

        # GIVEN - custom NotFoundError not in EXCEPTION_MAP
        class CustomNotFoundError(NotFoundError):
            pass

        exc = CustomNotFoundError("Resource not found")

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_404_NOT_FOUND
        assert detail == "Resource not found"

    def test_unknown_validation_error_uses_base_class_mapping(self):
        """
        GIVEN a ValidationError subclass not in EXCEPTION_MAP
        WHEN _get_status_and_detail is called
        THEN it falls back to ValidationError base class mapping
        """

        # GIVEN - custom ValidationError not in EXCEPTION_MAP
        class CustomValidationError(ValidationError):
            pass

        exc = CustomValidationError("Validation failed")

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert detail == "Validation failed"

    def test_unknown_become_api_error_uses_base_class_mapping(self):
        """
        GIVEN a BeCoMeAPIError subclass not in EXCEPTION_MAP
        WHEN _get_status_and_detail is called
        THEN it falls back to BeCoMeAPIError base class mapping (400)
        """

        # GIVEN - custom BeCoMeAPIError not in EXCEPTION_MAP
        class CustomAPIError(BeCoMeAPIError):
            pass

        exc = CustomAPIError("Something went wrong")

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_400_BAD_REQUEST
        assert detail == "Something went wrong"

    def test_base_become_api_error_uses_default(self):
        """
        GIVEN a plain BeCoMeAPIError instance
        WHEN _get_status_and_detail is called
        THEN it uses base class mapping (400)
        """
        # GIVEN
        exc = BeCoMeAPIError("Base error")

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_400_BAD_REQUEST
        assert detail == "Base error"
