from __future__ import annotations

import os
import re
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from fiobank import AsyncFioBank, HTTPError


BASE_URL = "https://fioapi.fio.cz/v1/rest/"


@pytest.fixture()
def token() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def transactions_text() -> str:
    with open(os.path.dirname(__file__) + "/transactions.json") as f:
        return f.read()


@pytest.fixture()
def client_decimal(token: str, transactions_text: str):
    with respx.mock(assert_all_called=False) as router:
        url = re.escape(BASE_URL) + rf"[^/]+/{token}/([^/]+/)*transactions\.json"
        router.get(url__regex=url).mock(
            return_value=httpx.Response(200, text=transactions_text)
        )

        url = re.escape(BASE_URL) + rf"set-last-\w+/{token}/[^/]+/"
        router.get(url__regex=url).mock(return_value=httpx.Response(200))

        yield AsyncFioBank(token, decimal=True)


async def test_info(client_decimal: AsyncFioBank):
    info = await client_decimal.info()

    assert info["balance"] == Decimal("2060.52")
    assert frozenset(info.keys()) == frozenset(
        [
            "account_number_full",
            "account_number",
            "bank_code",
            "currency",
            "iban",
            "bic",
            "balance",
        ]
    )


@pytest.mark.parametrize(
    "method, args, kwargs",
    [
        ("period", [date(2016, 8, 4), date(2016, 8, 30)], {}),
        ("period", ["2016-08-04", "2016-08-30"], {}),
        ("statement", [2016, 308], {}),
        ("last", [], {"from_id": 308}),
        ("last", [], {"from_date": date(2016, 8, 4)}),
        ("last", [], {"from_date": "2016-08-04"}),
    ],
)
async def test_transactions_integration(client_decimal, method, args, kwargs):
    gen = await getattr(client_decimal, method)(*args, **kwargs)

    count = 0
    for record in gen:
        count += 1
        assert "amount" in record

    assert count > 0


async def test_transactions(client_decimal: AsyncFioBank):
    info, transactions = await client_decimal.transactions("2016-08-04", "2016-08-30")
    transaction = next(transactions)
    assert transaction["amount"] == Decimal("-130.0")
    assert info["balance"] == Decimal("2060.52")


async def test_last_transactions(client_decimal: AsyncFioBank):
    info, transactions = await client_decimal.last_transactions(from_id=308)
    transaction = next(transactions)
    assert transaction["amount"] == Decimal("-130.0")
    assert info["balance"] == Decimal("2060.52")


async def test_last_statement(token: str, transactions_text: str):
    with respx.mock() as router:
        router.get(BASE_URL + f"lastStatement/{token}/statement").mock(
            return_value=httpx.Response(200, text="2017,12")
        )
        by_id = router.get(
            url__regex=re.escape(BASE_URL)
            + rf"by-id/{token}/[^/]+/[^/]+/transactions\.json"
        ).mock(return_value=httpx.Response(200, text=transactions_text))
        client = AsyncFioBank(token, decimal=True)

        transactions = list(await client.last_statement())

        assert len(transactions) > 0
        assert f"by-id/{token}/2017/12/transactions.json" in str(
            by_id.calls[0].request.url
        )


async def test_last_statement_none(token: str):
    with respx.mock() as router:
        router.get(BASE_URL + f"lastStatement/{token}/statement").mock(
            return_value=httpx.Response(200, text="null,null")
        )
        client = AsyncFioBank(token, decimal=True)

        with pytest.raises(ValueError, match="No data available"):
            await client.last_statement(2000)


async def test_409_conflict(token: str, transactions_text: str):
    with respx.mock() as router:
        url = re.escape(BASE_URL) + rf"[^/]+/{token}/([^/]+/)*transactions\.json"
        router.get(url__regex=url).mock(
            side_effect=[
                httpx.Response(409),
                httpx.Response(200, text=transactions_text),
            ]
        )
        client = AsyncFioBank(token, decimal=True)
        transactions = await client.last()
        transaction = next(transactions)

    assert transaction["amount"] == Decimal("-130.0")


async def test_http_error_with_token_redaction(token: str):
    response_body = f"Error occurred with token {token} in the response body"

    with respx.mock() as router:
        url = re.escape(BASE_URL) + rf"periods/{token}/[^/]+/[^/]+/transactions\.json"
        router.get(url__regex=url).mock(
            return_value=httpx.Response(400, text=response_body)
        )
        client = AsyncFioBank(token, decimal=True)

        with pytest.raises(HTTPError) as exc_info:
            await client.period("2025-01-01", "2025-02-01")

        assert exc_info.value.status_code == 400
        error_msg = str(exc_info.value)
        assert token not in error_msg
        assert "***TOKEN***" in error_msg
        assert "Error occurred with token ***TOKEN*** in the response body" in error_msg


async def test_last_conflicting_params():
    client = AsyncFioBank("...", decimal=True)
    with pytest.raises(ValueError):
        await client.last(from_id=308, from_date=date(2016, 8, 30))
