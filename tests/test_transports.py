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
        with HTTPXTransport() as transport:
            response = transport.get("https://example.test/")

    assert isinstance(response, Response)
    assert response.status_code == 201
    assert response.text == "hello"


async def test_httpx_async_transport_returns_response():
    with respx.mock() as router:
        router.get("https://example.test/").mock(
            return_value=httpx.Response(202, text="hello")
        )
        async with HTTPXAsyncTransport() as transport:
            response = await transport.get("https://example.test/")

    assert isinstance(response, Response)
    assert response.status_code == 202
    assert response.text == "hello"


def test_httpx_transport_close_owns_default_client():
    transport = HTTPXTransport()
    transport.close()
    assert transport.client.is_closed


def test_httpx_transport_close_leaves_injected_client_open():
    client = httpx.Client()
    transport = HTTPXTransport(client=client)
    transport.close()
    assert not client.is_closed
    client.close()


async def test_httpx_async_transport_aclose_owns_default_client():
    transport = HTTPXAsyncTransport()
    await transport.aclose()
    assert transport.client.is_closed


async def test_httpx_async_transport_aclose_leaves_injected_client_open():
    client = httpx.AsyncClient()
    transport = HTTPXAsyncTransport(client=client)
    await transport.aclose()
    assert not client.is_closed
    await client.aclose()


def test_fiobank_context_manager_closes_default_transport():
    with FioBank("token", decimal=True) as client:
        transport = client.transport
    assert transport.client.is_closed


async def test_async_fiobank_context_manager_closes_default_transport():
    async with AsyncFioBank("token", decimal=True) as client:
        transport = client.transport
    assert transport.client.is_closed


def test_fiobank_close_is_noop_for_transport_without_close():
    client = FioBank("token", decimal=True, transport=FakeTransport("{}"))
    client.close()  # must not raise even though FakeTransport has no close()


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
