"""Domain-specific exceptions for depot-butler.

This module defines a hierarchy of exceptions that represent different
failure scenarios in the depot-butler application. Using domain-specific
exceptions improves error handling by making it clear what kind of error
occurred and how it should be handled.
"""


class DepotButlerError(Exception):
    """Base exception for all depot-butler errors.

    All custom exceptions in the depot-butler application should inherit
    from this base class.
    """


class AuthenticationError(DepotButlerError):
    """Authentication failed - user action required.

    This exception indicates that authentication has failed and requires
    user intervention to resolve. This is typically a permanent failure
    that cannot be resolved by retrying.

    Examples:
        - Cookie expired or invalid
        - Invalid credentials provided
        - OAuth refresh token is invalid
        - Missing authentication configuration
    """


class TransientError(DepotButlerError):
    """Temporary failure - safe to retry.

    This exception indicates a temporary failure that may succeed if
    retried after a delay. The underlying service or resource is likely
    experiencing temporary issues.

    Examples:
        - Network timeout
        - Service temporarily unavailable (5xx errors)
        - Rate limit exceeded
        - Temporary network connectivity issues
    """


class PublicationNotFoundError(DepotButlerError):
    """Publication doesn't exist in the user's account.

    Raised when attempting to access a publication that is not available
    in the authenticated user's account or subscription.
    """


class EditionNotFoundError(DepotButlerError):
    """No edition available for the requested publication.

    Raised when a publication exists but has no available edition
    (e.g., not yet published, or edition is no longer available).
    """


class DownloadError(DepotButlerError):
    """Failed to download PDF file.

    Raised when downloading a publication PDF fails for any reason
    other than authentication or network issues.
    """


class UploadError(DepotButlerError):
    """Failed to upload file to OneDrive.

    Raised when uploading a file to OneDrive fails, excluding
    authentication errors which should raise AuthenticationError.
    """


class EmailDeliveryError(DepotButlerError):
    """Failed to send email.

    Raised when email delivery fails, including SMTP connection
    errors, authentication failures, or message rejection.
    """


class ConfigurationError(DepotButlerError):
    """Invalid or missing configuration.

    Raised when the application configuration is invalid or incomplete,
    preventing the application from functioning correctly.

    Examples:
        - Missing required environment variables
        - Invalid configuration values
        - Conflicting configuration settings
    """


class DatabaseError(DepotButlerError):
    """Database operation failed.

    Raised when a database operation fails, excluding transient
    connection issues which should raise TransientError.

    Examples:
        - Invalid query
        - Constraint violation
        - Data integrity issues
    """
