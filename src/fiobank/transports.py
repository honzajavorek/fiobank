from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Response:
    """Minimal HTTP response the rest of the library operates on.

    A transport only needs to report the status code and hand back the raw
    body bytes. Everything else (status interpretation, error messages, token
    sanitization, JSON decoding) is fiobank's own logic and lives in the
    client, shared by the sync and async variants.
    """

    status_code: int
    content: bytes

    @property
    def text(self) -> str:
        # Fio always returns UTF-8, so decoding here is deterministic and
        # avoids depending on any HTTP client's encoding guessing.
        return self.content.decode("utf-8")


class Transport(Protocol):
    """A synchronous transport does one thing: GET a URL."""

    def get(self, url: str, params: dict | None = None) -> Response: ...


class AsyncTransport(Protocol):
    """An asynchronous transport does one thing: GET a URL."""

    async def get(self, url: str, params: dict | None = None) -> Response: ...


class HTTPXTransport:
    """Default synchronous transport, backed by :mod:`httpx`."""

    def __init__(self, *, timeout: float = 60, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=timeout)

    def get(self, url: str, params: dict | None = None) -> Response:
        response = self.client.get(url, params=params)
        return Response(response.status_code, response.content)


class HTTPXAsyncTransport:
    """Default asynchronous transport, backed by :mod:`httpx`."""

    def __init__(self, *, timeout: float = 60, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=timeout)

    async def get(self, url: str, params: dict | None = None) -> Response:
        response = await self.client.get(url, params=params)
        return Response(response.status_code, response.content)
