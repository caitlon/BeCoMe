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
    """Raised when authentication fails."""


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


# Opinion-related exceptions
class OpinionNotFoundError(NotFoundError):
    """Raised when opinion is not found."""


class ValuesOutOfRangeError(ValidationError):
    """Raised when opinion values are outside project scale."""


class ScaleRangeError(ValidationError):
    """Raised when scale_min >= scale_max."""
