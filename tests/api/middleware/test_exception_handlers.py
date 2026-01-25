"""Tests for exception handlers."""

import asyncio
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, status

from api.exceptions import (
    BeCoMeAPIError,
    InvalidCredentialsError,
    NotFoundError,
    ProjectNotFoundError,
    ValidationError,
    ValuesOutOfRangeError,
)
from api.middleware.exception_handlers import (
    _get_status_and_detail,
    become_api_error_handler,
    register_exception_handlers,
)


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

    def test_known_exception_uses_exact_mapping(self):
        """
        GIVEN an exception type that exists in EXCEPTION_MAP
        WHEN _get_status_and_detail is called
        THEN it returns the mapped status code and message
        """
        # GIVEN
        exc = ProjectNotFoundError("Project 123 not found")

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_404_NOT_FOUND
        assert detail == "Project not found"  # From MAP, not exception message

    def test_exception_with_none_detail_uses_message(self):
        """
        GIVEN an exception with None detail in EXCEPTION_MAP
        WHEN _get_status_and_detail is called
        THEN it uses the exception message as detail
        """
        # GIVEN
        exc = ValuesOutOfRangeError("Values 1, 5, 10 are outside range [0, 7]")

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert detail == "Values 1, 5, 10 are outside range [0, 7]"


class TestBecomeApiErrorHandler:
    """Tests for become_api_error_handler function."""

    def test_returns_json_response_with_correct_status(self):
        """
        GIVEN a BeCoMeAPIError
        WHEN become_api_error_handler is called
        THEN it returns JSONResponse with correct status and detail
        """
        # GIVEN
        request = MagicMock()
        exc = ProjectNotFoundError("Project 123 not found")

        # WHEN
        response = asyncio.run(become_api_error_handler(request, exc))

        # THEN
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.body == b'{"detail":"Project not found"}'

    def test_invalid_credentials_adds_www_authenticate_header(self):
        """
        GIVEN an InvalidCredentialsError
        WHEN become_api_error_handler is called
        THEN it adds WWW-Authenticate header to response
        """
        # GIVEN
        request = MagicMock()
        exc = InvalidCredentialsError()

        # WHEN
        response = asyncio.run(become_api_error_handler(request, exc))

        # THEN
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_credentials_with_email_logs_failure(self):
        """
        GIVEN an InvalidCredentialsError with email
        WHEN become_api_error_handler is called
        THEN it logs the failed login attempt
        """
        # GIVEN
        request = MagicMock()
        exc = InvalidCredentialsError(
            email="test@example.com",
            reason="invalid_password",
        )

        with patch(
            "api.middleware.exception_handlers.log_login_failure"
        ) as mock_log:
            # WHEN
            asyncio.run(become_api_error_handler(request, exc))

            # THEN
            mock_log.assert_called_once_with(
                "test@example.com",
                "invalid_password",
                request,
            )

    def test_invalid_credentials_without_email_skips_logging(self):
        """
        GIVEN an InvalidCredentialsError without email
        WHEN become_api_error_handler is called
        THEN it does not log the attempt
        """
        # GIVEN
        request = MagicMock()
        exc = InvalidCredentialsError()  # No email

        with patch(
            "api.middleware.exception_handlers.log_login_failure"
        ) as mock_log:
            # WHEN
            asyncio.run(become_api_error_handler(request, exc))

            # THEN
            mock_log.assert_not_called()


class TestRegisterExceptionHandlers:
    """Tests for register_exception_handlers function."""

    def test_registers_handler_for_become_api_error(self):
        """
        GIVEN a FastAPI app
        WHEN register_exception_handlers is called
        THEN it registers become_api_error_handler for BeCoMeAPIError
        """
        # GIVEN
        app = FastAPI()

        # WHEN
        register_exception_handlers(app)

        # THEN
        assert BeCoMeAPIError in app.exception_handlers
        assert app.exception_handlers[BeCoMeAPIError] == become_api_error_handler
