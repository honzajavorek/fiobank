from __future__ import annotations

from decimal import Decimal

import httpx

from fiobank import (
    AsyncFioBank,
    FioBank,
    HTTPXAsyncTransport,
    HTTPXTransport,
    Response,
)


def test_response_text_decodes_utf8():
    response = Response(200, "Vilém Fusek".encode())
    assert response.text == "Vilém Fusek"


def test_httpx_transport_returns_response():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(201, text="hello"))
    )
    transport = HTTPXTransport(client=client)

    response = transport.get("https://example.test/")
    transport.close()

    assert isinstance(response, Response)
    assert response.status_code == 201
    assert response.text == "hello"


async def test_httpx_async_transport_returns_response():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(202, text="hello"))
    )
    transport = HTTPXAsyncTransport(client=client)

    response = await transport.get("https://example.test/")
    await transport.aclose()

    assert isinstance(response, Response)
    assert response.status_code == 202
    assert response.text == "hello"


def test_httpx_transport_close_closes_client():
    transport = HTTPXTransport()
    transport.close()
    assert transport.client.is_closed


async def test_httpx_async_transport_aclose_closes_client():
    transport = HTTPXAsyncTransport()
    await transport.aclose()
    assert transport.client.is_closed


def test_fiobank_context_manager_closes_transport():
    with FioBank("token", decimal=True) as client:
        transport = client.transport
    assert transport.client.is_closed


async def test_async_fiobank_context_manager_closes_transport():
    async with AsyncFioBank("token", decimal=True) as client:
        transport = client.transport
    assert transport.client.is_closed


class FakeTransport:
    """A custom transport implementing the ``Transport`` protocol without
    touching the network -- exactly the pluggability issue #45 is about."""

    def __init__(self, body: str):
        self.body = body
        self.requests: list[str] = []
        self.closed = False

    def get(self, url: str) -> Response:
        self.requests.append(url)
        return Response(200, self.body.encode())

    def close(self) -> None:
        self.closed = True


def test_custom_transport_is_used_and_closed(transactions_text: str):
    transport = FakeTransport(transactions_text)

    with FioBank("token", decimal=True, transport=transport) as client:
        transaction = next(client.last())

    assert transaction["amount"] == Decimal("-130.0")
    assert all("token" in url for url in transport.requests)
    assert transport.closed


class FakeAsyncTransport:
    def __init__(self, body: str):
        self.body = body
        self.closed = False

    async def get(self, url: str) -> Response:
        return Response(200, self.body.encode())

    async def aclose(self) -> None:
        self.closed = True


async def test_custom_async_transport_is_used_and_closed(transactions_text: str):
    transport = FakeAsyncTransport(transactions_text)

    async with AsyncFioBank("token", decimal=True, transport=transport) as client:
        transactions = await client.last()

    assert next(transactions)["amount"] == Decimal("-130.0")
    assert transport.closed
