from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable

import httpx
import pytest

from fiobank import AsyncFioBank, FioBank, HTTPXAsyncTransport, HTTPXTransport


BASE_URL = "https://fioapi.fio.cz/v1/rest/"

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture()
def token() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def transactions_text() -> str:
    with open(os.path.dirname(__file__) + "/transactions.json") as f:
        return f.read()


@pytest.fixture()
def transactions_json() -> dict:
    with open(os.path.dirname(__file__) + "/transactions.json") as f:
        return json.load(f)


@pytest.fixture()
def sync_client(token: str):
    """Build a ``FioBank`` whose transport is driven by an httpx MockTransport.

    The handler receives each ``httpx.Request`` and returns an
    ``httpx.Response``, so tests stay independent of any real network.
    """

    def make(handler: Handler, *, decimal: bool = True) -> FioBank:
        client = httpx.Client(transport=httpx.MockTransport(handler))
        return FioBank(token, decimal=decimal, transport=HTTPXTransport(client=client))

    return make


@pytest.fixture()
def async_client(token: str):
    """``sync_client`` counterpart for :class:`AsyncFioBank`."""

    def make(handler: Handler, *, decimal: bool = True) -> AsyncFioBank:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return AsyncFioBank(
            token, decimal=decimal, transport=HTTPXAsyncTransport(client=client)
        )

    return make


@pytest.fixture()
def transactions_handler(transactions_text: str) -> Handler:
    """A handler serving the sample statement for any transactions request and
    an empty body for the ``set-last-*`` cursor endpoints."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("transactions.json"):
            return httpx.Response(200, text=transactions_text)
        if "set-last-" in path:
            return httpx.Response(200)
        raise AssertionError(f"unexpected request: {request.url}")

    return handler
