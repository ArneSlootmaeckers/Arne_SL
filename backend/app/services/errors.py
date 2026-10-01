"""Service-layer exceptions. The API layer maps each of these to an HTTP status
code (see app/main.py) so services stay framework-free.
"""
from __future__ import annotations


class DomainServiceError(Exception):
    """Base class for service errors that the API layer translates to HTTP responses."""


class NoPendingScanError(DomainServiceError):
    """A verdict/acknowledgement was submitted with no matching open scan."""


class WrongResolutionPathError(DomainServiceError):
    """A verdict/acknowledgement was submitted via the wrong endpoint for the pending status."""


class InvalidPincodeError(DomainServiceError):
    """No active employee matches the given pincode."""


class SessionExpiredError(DomainServiceError):
    """The admin session is missing, expired, or belongs to a revoked employee."""


class PermissionDeniedError(DomainServiceError):
    """The authenticated employee's role does not allow this action."""


class DuplicatePincodeError(DomainServiceError):
    """The requested pincode is already in use by another active employee."""


class EmployeeNotFoundError(DomainServiceError):
    """No employee exists with the given id."""
