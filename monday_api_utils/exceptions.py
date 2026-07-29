"""Custom exceptions for monday_api_utils."""


class MondayApiError(Exception):
    """Raised when the monday.com API returns an error response."""

    def __init__(self, message: str, errors: list | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class MondayAuthError(MondayApiError):
    """Raised when authentication with the monday.com API fails."""
