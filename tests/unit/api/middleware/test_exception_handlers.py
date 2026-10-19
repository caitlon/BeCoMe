"""Tests for exception handlers."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError

from api.exceptions import (
    AlreadyInvitedError,
    BeCoMeAPIError,
    CurrentPasswordIncorrectError,
    DisposableEmailDomainError,
    EmailNotVerifiedError,
    ExampleProjectInvitationError,
    InvalidCredentialsError,
    InvitationNotFoundError,
    NotFoundError,
    PhotoContentMismatchError,
    PhotoDimensionsTooLargeError,
    PhotoTooLargeError,
    PhotoTypeNotAllowedError,
    PhotoUnreadableError,
    ProjectNotFoundError,
    ScaleExcludesOpinionsError,
    TurnstileVerificationError,
    UnresolvableEmailDomainError,
    UserAlreadyMemberError,
    UserNotFoundForInvitationError,
    ValidationError,
    ValuesOutOfRangeError,
)
from api.middleware.exception_handlers import (
    CURRENT_PASSWORD_INCORRECT_CODE,
    SCALE_EXCLUDES_OPINIONS_CODE,
    TURNSTILE_REFUSED_CODE,
    _get_status_and_detail,
    become_api_error_handler,
    register_exception_handlers,
    request_validation_error_handler,
    unhandled_exception_handler,
)


class TestGetStatusAndDetail:
    """Tests for _get_status_and_detail function."""

    def test_unknown_not_found_error_uses_base_class_mapping(self):
        """
        GIVEN a NotFoundError subclass not in EXCEPTION_MAP
        WHEN _get_status_and_detail is called
        THEN it falls back to NotFoundError base class mapping
        """

        # GIVEN: custom NotFoundError not in EXCEPTION_MAP
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

        # GIVEN: custom ValidationError not in EXCEPTION_MAP
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

        # GIVEN: custom BeCoMeAPIError not in EXCEPTION_MAP
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


class TestEmailPolicyExceptionMapping:
    """Tests for the disposable/MX email-policy exception mappings.

    Both map to 400 with their own distinguishable copy, and neither reveals
    the underlying exception message (which carries the raw domain).
    """

    def test_disposable_email_domain_error_maps_to_400_with_its_own_copy(self):
        """
        GIVEN a DisposableEmailDomainError
        WHEN _get_status_and_detail is called
        THEN it maps to 400 with the disposable-address copy, not the raw message
        """
        # GIVEN
        exc = DisposableEmailDomainError("disposable email domain: mailinator.com")

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_400_BAD_REQUEST
        assert detail == "That looks like a temporary address"
        assert "mailinator.com" not in detail

    def test_unresolvable_email_domain_error_maps_to_400_with_its_own_copy(self):
        """
        GIVEN an UnresolvableEmailDomainError
        WHEN _get_status_and_detail is called
        THEN it maps to 400 with the unresolvable-domain copy, not the raw message
        """
        # GIVEN
        exc = UnresolvableEmailDomainError(
            "domain has no mail-capable DNS records: doesnotexist.invalid"
        )

        # WHEN
        status_code, detail = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_400_BAD_REQUEST
        assert detail == "We could not find that domain. Check for a typo."
        assert "doesnotexist.invalid" not in detail

    def test_the_two_email_policy_messages_are_distinguishable(self):
        """
        GIVEN both email-policy exceptions
        WHEN mapped to a detail message
        THEN the two messages differ, so the caller can tell the reasons apart
        """
        # GIVEN
        disposable = DisposableEmailDomainError("disposable email domain: mailinator.com")
        unresolvable = UnresolvableEmailDomainError("domain has no mail-capable DNS records: x")

        # WHEN
        _, disposable_detail = _get_status_and_detail(disposable)
        _, unresolvable_detail = _get_status_and_detail(unresolvable)

        # THEN
        assert disposable_detail != unresolvable_detail


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
        response = become_api_error_handler(request, exc)

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
        response = become_api_error_handler(request, exc)

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

        with patch("api.middleware.exception_handlers.log_login_failure") as mock_log:
            # WHEN
            become_api_error_handler(request, exc)

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

        with patch("api.middleware.exception_handlers.log_login_failure") as mock_log:
            # WHEN
            become_api_error_handler(request, exc)

            # THEN
            mock_log.assert_not_called()

    def test_wrong_current_password_logs_password_change_failure(self):
        """
        GIVEN a wrong current password on a password change
        WHEN become_api_error_handler is called
        THEN it logs a password-change failure, not a login failure
        """
        # GIVEN
        request = MagicMock()
        exc = CurrentPasswordIncorrectError("Current password is incorrect")

        with (
            patch("api.middleware.exception_handlers.log_password_change_failure") as mock_pcf,
            patch("api.middleware.exception_handlers.log_login_failure") as mock_lf,
        ):
            # WHEN
            become_api_error_handler(request, exc)

            # THEN
            mock_pcf.assert_called_once_with(request)
            mock_lf.assert_not_called()

    def test_invalid_credentials_does_not_log_password_change_failure(self):
        """
        GIVEN a failed login
        WHEN become_api_error_handler is called
        THEN no password-change failure is logged
        """
        # GIVEN
        request = MagicMock()
        exc = InvalidCredentialsError(email="test@example.com", reason="invalid_password")

        with (
            patch("api.middleware.exception_handlers.log_password_change_failure") as mock_pcf,
            patch("api.middleware.exception_handlers.log_login_failure"),
        ):
            # WHEN
            become_api_error_handler(request, exc)

            # THEN
            mock_pcf.assert_not_called()


class TestMachineReadableErrorCodes:
    """A 403 the SPA has to act on differently carries a code, not just a status.

    ``POST /auth/login`` can answer 403 for two unrelated reasons: the account is
    unverified, and the bot check refused the request. They need different screens, and
    the only thing separating them in the body used to be an English sentence. Matching
    that sentence in the SPA would break on any rewording, so the discriminator is a
    stable code the client can compare.
    """

    def test_a_turnstile_refusal_carries_a_code(self):
        """
        GIVEN the bot check refused a request
        WHEN the handler builds the response
        THEN the body carries the machine-readable turnstile code beside the detail
        """
        # GIVEN
        request = MagicMock()
        exc = TurnstileVerificationError("turnstile check refused the request: rejected")

        # WHEN
        response = become_api_error_handler(request, exc)

        # THEN
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert json.loads(response.body)["code"] == TURNSTILE_REFUSED_CODE

    def test_a_scale_change_that_excludes_opinions_is_a_409_with_a_code(self):
        """
        GIVEN a scale change that would leave an opinion outside the new range
        WHEN the handler builds the response
        THEN it answers 409 with the fixed detail and the scale code, never the message
        """
        # GIVEN
        request = MagicMock()
        exc = ScaleExcludesOpinionsError("2 opinion(s) fall outside the scale 40.0..80.0")

        # WHEN
        response = become_api_error_handler(request, exc)

        # THEN
        assert response.status_code == status.HTTP_409_CONFLICT
        assert json.loads(response.body) == {
            "detail": (
                "Existing opinions fall outside the new scale. "
                "Widen the range, or ask the experts to change their opinions first."
            ),
            "code": SCALE_EXCLUDES_OPINIONS_CODE,
        }

    def test_a_wrong_current_password_is_a_400_with_a_code_and_no_challenge(self):
        """
        GIVEN a password change with a wrong current password
        WHEN the handler builds the response
        THEN it answers 400 with the code and no WWW-Authenticate header

        A 401 on an authenticated request reads as "no session" to the SPA, which would
        refresh, retry and sign the user out over a typo.
        """
        # GIVEN
        request = MagicMock()
        exc = CurrentPasswordIncorrectError("Current password is incorrect")

        # WHEN
        response = become_api_error_handler(request, exc)

        # THEN
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert json.loads(response.body) == {
            "detail": "Current password is incorrect",
            "code": CURRENT_PASSWORD_INCORRECT_CODE,
        }
        assert "www-authenticate" not in response.headers

    def test_an_unverified_account_carries_no_code(self):
        """
        GIVEN a login blocked because the account is not verified
        WHEN the handler builds the response
        THEN the body carries no code, which is what the SPA reads as this case

        A 403 with no code is also what an older API answers, so the SPA treating it as
        the unverified case keeps working while the two services deploy separately.
        """
        # GIVEN
        request = MagicMock()
        exc = EmailNotVerifiedError("unverified")

        # WHEN
        response = become_api_error_handler(request, exc)

        # THEN
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "code" not in json.loads(response.body)

    def test_no_token_and_a_rejected_token_carry_the_same_code(self):
        """
        GIVEN one refusal for a missing header and one for a token that failed
        WHEN the handler builds both responses
        THEN the two bodies are identical, code included

        The code tells the SPA which screen to draw. It must not also tell a caller
        which half of the check they failed, or whether it is switched on.
        """
        # GIVEN
        request = MagicMock()

        # WHEN
        absent = become_api_error_handler(
            request,
            TurnstileVerificationError("turnstile check refused the request: missing_token"),
        )
        rejected = become_api_error_handler(
            request, TurnstileVerificationError("turnstile check refused the request: rejected")
        )

        # THEN
        assert json.loads(absent.body) == json.loads(rejected.body)


class TestInvitationAndPhotoErrorCodes:
    """Each invitation and photo-upload refusal answers with its own stable code.

    So the SPA can translate these by code, a code names exactly one (status, detail) pair
    and the sentence stays as it was for any client still matching on it.
    """

    @pytest.mark.parametrize(
        ("exc", "expected_status", "detail", "code"),
        [
            (
                UserNotFoundForInvitationError("No user found with email x@example.com"),
                status.HTTP_404_NOT_FOUND,
                "No user found with this email",
                "invitee_not_found",
            ),
            (
                AlreadyInvitedError("User already has a pending invitation"),
                status.HTTP_409_CONFLICT,
                "User already has a pending invitation",
                "already_invited",
            ),
            (
                UserAlreadyMemberError("User is already a member of this project"),
                status.HTTP_409_CONFLICT,
                "You are already a member of this project",
                "already_member",
            ),
            (
                ExampleProjectInvitationError("The example project cannot take invitations"),
                status.HTTP_409_CONFLICT,
                "The example project cannot take invitations",
                "example_project_not_invitable",
            ),
            (
                InvitationNotFoundError("Invitation not found"),
                status.HTTP_404_NOT_FOUND,
                "Invitation not found",
                "invitation_not_found",
            ),
            (
                PhotoTypeNotAllowedError("content type refused"),
                status.HTTP_400_BAD_REQUEST,
                "Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
                "photo_type_not_allowed",
            ),
            (
                PhotoTooLargeError("file over the limit"),
                status.HTTP_400_BAD_REQUEST,
                "File too large. Maximum size is 5 MB",
                "photo_too_large",
            ),
            (
                PhotoContentMismatchError("magic bytes disagree"),
                status.HTTP_400_BAD_REQUEST,
                "File content does not match declared type",
                "photo_content_mismatch",
            ),
            (
                PhotoDimensionsTooLargeError("canvas over the limit"),
                status.HTTP_400_BAD_REQUEST,
                "Image dimensions are too large. Maximum is 8192 pixels per side "
                "and about 16.7 megapixels in total",
                "photo_dimensions_too_large",
            ),
            (
                PhotoUnreadableError("header does not parse"),
                status.HTTP_400_BAD_REQUEST,
                "The image could not be read. Try saving it again as JPEG or PNG.",
                "photo_unreadable",
            ),
        ],
    )
    def test_refusal_answers_with_its_status_detail_and_code(
        self, exc, expected_status, detail, code
    ):
        """
        GIVEN an invitation or photo-upload refusal
        WHEN the handler builds the response
        THEN the body is exactly the fixed detail plus the refusal's own code
        """
        # GIVEN
        request = MagicMock()

        # WHEN
        response = become_api_error_handler(request, exc)

        # THEN
        assert response.status_code == expected_status
        assert json.loads(response.body) == {"detail": detail, "code": code}

    def test_an_unknown_invitee_response_does_not_echo_the_address(self):
        """
        GIVEN the service message for an unknown invitee, which names the address
        WHEN the handler builds the response
        THEN the address appears nowhere in the body

        Without a mapped detail the handler would fall back to the exception message.
        """
        # GIVEN
        request = MagicMock()
        exc = UserNotFoundForInvitationError("No user found with email stranger@example.com")

        # WHEN
        response = become_api_error_handler(request, exc)

        # THEN
        assert b"stranger@example.com" not in response.body

    def test_a_pending_invitation_is_a_409_not_the_unmapped_422(self):
        """
        GIVEN AlreadyInvitedError, a ValidationError subclass
        WHEN its status is looked up
        THEN it is 409, not the 422 an unmapped ValidationError would get
        """
        # GIVEN
        exc = AlreadyInvitedError("User already has a pending invitation")

        # WHEN
        status_code, _ = _get_status_and_detail(exc)

        # THEN
        assert status_code == status.HTTP_409_CONFLICT


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


class TestExceptionLogging:
    """Tests that handled API errors are logged with context."""

    def test_logs_client_error_as_warning(self):
        """
        GIVEN a 4xx BeCoMeAPIError
        WHEN become_api_error_handler runs
        THEN it logs a WARNING carrying request_id, status, path and type
        """
        # GIVEN
        request = MagicMock()
        request.state.request_id = "rid-1"
        request.url.path = "/projects/123"
        exc = ProjectNotFoundError("Project 123 not found")

        # WHEN
        with patch("api.middleware.exception_handlers.logger") as mock_logger:
            become_api_error_handler(request, exc)

        # THEN
        mock_logger.warning.assert_called_once()
        extra = mock_logger.warning.call_args[1]["extra"]
        assert extra["status_code"] == status.HTTP_404_NOT_FOUND
        assert extra["request_id"] == "rid-1"
        assert extra["path"] == "/projects/123"
        assert extra["exception_type"] == "ProjectNotFoundError"


class TestRequestValidationErrorHandler:
    """Tests for the request validation error handler."""

    @staticmethod
    def _error(input_value, loc=("body", "scale_min")):
        return RequestValidationError(
            [
                {
                    "type": "finite_number",
                    "loc": loc,
                    "msg": "Input should be finite",
                    "input": input_value,
                }
            ]
        )

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(float("nan"), "nan"), (float("inf"), "inf"), (float("-inf"), "-inf")],
    )
    def test_top_level_non_finite_input_is_stringified(self, value, expected):
        """
        GIVEN a validation error whose rejected input is a non-finite float
        WHEN request_validation_error_handler runs
        THEN it returns 422 with the input as a string instead of failing to render
        """
        # GIVEN
        exc = self._error(value)

        # WHEN
        response = request_validation_error_handler(MagicMock(), exc)

        # THEN
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert json.loads(response.body)["detail"][0]["input"] == expected

    def test_nested_non_finite_input_is_stringified(self):
        """
        GIVEN a validation error whose rejected input holds non-finite floats at depth
        WHEN request_validation_error_handler runs
        THEN every one of them is stringified and finite values are untouched
        """
        # GIVEN
        exc = self._error({"peak": float("nan"), "bounds": [1.5, float("inf"), [float("-inf")]]})

        # WHEN
        response = request_validation_error_handler(MagicMock(), exc)

        # THEN
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert json.loads(response.body)["detail"][0]["input"] == {
            "peak": "nan",
            "bounds": [1.5, "inf", ["-inf"]],
        }

    def test_ordinary_error_body_matches_fastapi_default(self):
        """
        GIVEN an ordinary validation error with no non-finite value
        WHEN request_validation_error_handler runs
        THEN its body equals what FastAPI's default handler produces
        """
        # GIVEN
        exc = self._error("abc", loc=("body", "name"))

        # WHEN
        response = request_validation_error_handler(MagicMock(), exc)

        # THEN
        default = asyncio.run(request_validation_exception_handler(MagicMock(), exc))
        assert response.status_code == default.status_code
        assert json.loads(response.body) == json.loads(default.body)

    def test_register_adds_validation_handler(self):
        """
        GIVEN a FastAPI app
        WHEN register_exception_handlers runs
        THEN request_validation_error_handler is registered for RequestValidationError
        """
        # GIVEN
        app = FastAPI()

        # WHEN
        register_exception_handlers(app)

        # THEN
        assert app.exception_handlers[RequestValidationError] == request_validation_error_handler


class TestUnhandledExceptionHandler:
    """Tests for the catch-all exception handler."""

    def test_returns_500_with_generic_detail(self):
        """
        GIVEN an unexpected exception
        WHEN unhandled_exception_handler runs
        THEN it returns a 500 response with a generic detail
        """
        # GIVEN
        request = MagicMock()
        request.state.request_id = "rid-2"
        request.url.path = "/boom"
        exc = RuntimeError("kaboom")

        # WHEN
        with patch("api.middleware.exception_handlers.logger"):
            response = unhandled_exception_handler(request, exc)

        # THEN
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.body == b'{"detail":"Internal server error"}'

    def test_logs_error_with_traceback(self):
        """
        GIVEN an unexpected exception
        WHEN unhandled_exception_handler runs
        THEN it logs at ERROR level with the traceback attached
        """
        # GIVEN
        request = MagicMock()
        request.state.request_id = "rid-2"
        request.url.path = "/boom"
        exc = RuntimeError("kaboom")

        # WHEN
        with patch("api.middleware.exception_handlers.logger") as mock_logger:
            unhandled_exception_handler(request, exc)

        # THEN
        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args[1]["exc_info"] is exc

    def test_register_adds_catch_all_handler(self):
        """
        GIVEN a FastAPI app
        WHEN register_exception_handlers runs
        THEN a handler is registered for the base Exception type
        """
        # GIVEN
        app = FastAPI()

        # WHEN
        register_exception_handlers(app)

        # THEN
        assert Exception in app.exception_handlers

    def test_catch_all_handles_unexpected_error_end_to_end(self):
        """
        GIVEN an app whose endpoint raises an unexpected error
        WHEN the endpoint is called through the full stack
        THEN the catch-all returns a 500 JSON response
        """
        # GIVEN
        from fastapi.testclient import TestClient

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/explode")
        def explode():
            raise RuntimeError("kaboom")

        live_client = TestClient(app, raise_server_exceptions=False)

        # WHEN
        response = live_client.get("/explode")

        # THEN
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {"detail": "Internal server error"}
