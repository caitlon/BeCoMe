"""API exception hierarchy.

All custom exceptions for the API layer are defined here.
"""


class BeCoMeAPIError(Exception):
    """Base exception for all API errors."""


class NotFoundError(BeCoMeAPIError):
    """Base exception for resource not found errors."""


class ValidationError(BeCoMeAPIError):
    """Base exception for validation errors."""


# User-related exceptions
class UserExistsError(ValidationError):
    """Raised when trying to create a user with existing email."""


class InvalidCredentialsError(BeCoMeAPIError):
    """Raised when authentication fails.

    :param message: Error message
    :param email: Email address that was attempted (for logging)
    :param reason: Failure reason for logging (user_not_found, invalid_password)
    """

    def __init__(
        self,
        message: str = "Invalid credentials",
        email: str | None = None,
        reason: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.email = email
        self.reason = reason


# Project-related exceptions
class ProjectNotFoundError(NotFoundError):
    """Raised when project is not found."""


class MemberNotFoundError(NotFoundError):
    """Raised when member is not found in project."""


# Invitation-related exceptions
class InvitationNotFoundError(NotFoundError):
    """Raised when invitation is not found."""


class InvitationExpiredError(ValidationError):
    """Raised when invitation has expired."""


class InvitationAlreadyUsedError(ValidationError):
    """Raised when invitation has already been used."""


class UserAlreadyMemberError(ValidationError):
    """Raised when user is already a member of the project."""


class UserNotFoundForInvitationError(NotFoundError):
    """Raised when user with specified email is not found for invitation."""


class AlreadyInvitedError(ValidationError):
    """Raised when user already has a pending invitation to the project."""


# Opinion-related exceptions
class OpinionNotFoundError(NotFoundError):
    """Raised when opinion is not found."""


class ValuesOutOfRangeError(ValidationError):
    """Raised when opinion values are outside project scale."""


class ScaleRangeError(ValidationError):
    """Raised when scale_min >= scale_max."""
