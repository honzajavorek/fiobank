from __future__ import annotations


class ThrottlingError(Exception):
    """Throttling error raised when the API is being used too fast."""

    def __str__(self) -> str:
        return "Token can be used only once per 30s"
