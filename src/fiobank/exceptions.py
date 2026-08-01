from __future__ import annotations


class ThrottlingError(Exception):
    """Throttling error raised when the API is being used too fast."""

    def __str__(self) -> str:
        return "Token can be used only once per 30s"


class HTTPError(Exception):
    """Raised for non-2xx HTTP responses.

    Replaces the ``requests.HTTPError`` that older versions leaked. The
    message has the API token redacted; ``status_code`` carries the HTTP
    status of the offending response.
    """

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
