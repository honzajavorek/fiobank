from __future__ import annotations

import os
from decimal import Decimal

import httpx
import pytest
import respx

from fiobank import (
    AsyncFioBank,
    FioBank,
    HTTPXAsyncTransport,
    HTTPXTransport,
    Response,
)


BASE_URL = "https://fioapi.fio.cz/v1/rest/"


@pytest.fixture()
def transactions_text() -> str:
    with open(os.path.dirname(__file__) + "/transactions.json") as f:
        return f.read()


def test_response_text_decodes_utf8():
    response = Response(200, "Vilém Fusek".encode())
    assert response.text == "Vilém Fusek"


def test_httpx_transport_returns_response():
    with respx.mock() as router:
        router.get("https://example.test/").mock(
            return_value=httpx.Response(201, text="hello")
        )
        transport = HTTPXTransport()
        response = transport.get("https://example.test/")

    assert isinstance(response, Response)
    assert response.status_code == 201
    assert response.text == "hello"


async def test_httpx_async_transport_returns_response():
    with respx.mock() as router:
        router.get("https://example.test/").mock(
            return_value=httpx.Response(202, text="hello")
        )
        transport = HTTPXAsyncTransport()
        response = await transport.get("https://example.test/")

    assert isinstance(response, Response)
    assert response.status_code == 202
    assert response.text == "hello"


class FakeTransport:
    """A custom transport implementing the ``Transport`` protocol without
    touching the network -- exactly the pluggability issue #45 is about."""

    def __init__(self, body: str):
        self.body = body
        self.requests: list[tuple[str, dict | None]] = []

    def get(self, url: str, params: dict | None = None) -> Response:
        self.requests.append((url, params))
        return Response(200, self.body.encode("utf-8"))


def test_custom_transport_is_used(transactions_text: str):
    transport = FakeTransport(transactions_text)
    client = FioBank("token", decimal=True, transport=transport)

    transaction = next(client.last())

    assert transaction["amount"] == Decimal("-130.0")
    assert transport.requests  # the custom transport did the work
    assert all("token" in url for url, _ in transport.requests)


class FakeAsyncTransport:
    def __init__(self, body: str):
        self.body = body

    async def get(self, url: str, params: dict | None = None) -> Response:
        return Response(200, self.body.encode("utf-8"))


async def test_custom_async_transport_is_used(transactions_text: str):
    transport = FakeAsyncTransport(transactions_text)
    client = AsyncFioBank("token", decimal=True, transport=transport)

    transactions = await client.last()

    assert next(transactions)["amount"] == Decimal("-130.0")
