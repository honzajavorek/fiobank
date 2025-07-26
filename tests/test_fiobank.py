from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest
import requests
import responses
from responses.registries import OrderedRegistry

from fiobank import FioBank
from fiobank.utils import coerce_date


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
def client_float(token: str, transactions_text: str):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as resps:
        url = re.compile(
            re.escape(FioBank.base_url) + rf"[^/]+/{token}/([^/]+/)*transactions\.json"
        )
        resps.add(responses.GET, url, body=transactions_text)

        url = re.compile(re.escape(FioBank.base_url) + rf"set-last-\w+/{token}/[^/]+/")
        resps.add(responses.GET, url)

        yield FioBank(token)


@pytest.fixture()
def client_decimal(token: str, transactions_text: str):
    with responses.RequestsMock(assert_all_requests_are_fired=False) as resps:
        url = re.compile(
            re.escape(FioBank.base_url) + rf"[^/]+/{token}/([^/]+/)*transactions\.json"
        )
        resps.add(responses.GET, url, body=transactions_text)

        url = re.compile(re.escape(FioBank.base_url) + rf"set-last-\w+/{token}/[^/]+/")
        resps.add(responses.GET, url)

        yield FioBank(token, decimal=True)


def test_client_decimal(client_decimal: FioBank):
    transaction = next(client_decimal.last())
    info = client_decimal.info()

    assert client_decimal.float_type is Decimal
    assert transaction["amount"] == Decimal("-130.0")
    assert info["balance"] == Decimal("2060.52")


def test_info_integration(client_float: FioBank):
    assert frozenset(client_float.info().keys()) == frozenset(
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


def test_info_uses_today(transactions_json: dict):
    client = FioBank("...")
    today = date.today()

    with mock.patch.object(client, "_request", return_value=transactions_json) as stub:
        client.info()
        stub.assert_called_once_with("periods", from_date=today, to_date=today)


def test_info_is_case_insensitive(transactions_json):
    client = FioBank("...")

    api_info = transactions_json["accountStatement"]["info"]
    value = api_info["accountId"]
    del api_info["accountId"]
    api_info["acCOUNTid"] = value

    sdk_info = client._parse_info(transactions_json)

    assert sdk_info["account_number"] == value


@pytest.mark.parametrize(
    "api_key, sdk_key",
    [
        ("accountId", "account_number"),
        ("bankId", "bank_code"),
        ("currency", "currency"),
        ("iban", "iban"),
        ("bic", "bic"),
        ("closingBalance", "balance"),
    ],
)
def test_info_parse(transactions_json, api_key, sdk_key):
    client = FioBank("...")

    api_info = transactions_json["accountStatement"]["info"]
    sdk_info = client._parse_info(transactions_json)

    assert sdk_info[sdk_key] == api_info[api_key]


def test_info_parse_account_number_full(transactions_json):
    client = FioBank("...")

    api_info = transactions_json["accountStatement"]["info"]
    sdk_info = client._parse_info(transactions_json)

    expected_value = "{}/{}".format(api_info["accountId"], api_info["bankId"])
    assert sdk_info["account_number_full"] == expected_value


def test_info_parse_no_account_number_full(transactions_json):
    client = FioBank("...")

    api_info = transactions_json["accountStatement"]["info"]
    del api_info["bankId"]

    sdk_info = client._parse_info(transactions_json)

    assert sdk_info["account_number_full"] is None


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
def test_transactions_integration(client_float, method, args, kwargs):
    gen = getattr(client_float, method)(*args, **kwargs)

    count = 0
    for record in gen:
        count += 1
        assert frozenset(record.keys()) == frozenset(
            [
                "transaction_id",
                "date",
                "amount",
                "currency",
                "account_number",
                "account_name",
                "bank_code",
                "bic",
                "bank_name",
                "constant_symbol",
                "variable_symbol",
                "specific_symbol",
                "user_identification",
                "recipient_message",
                "type",
                "executor",
                "specification",
                "comment",
                "instruction_id",
                "account_number_full",
                "original_amount",
                "original_currency",
                "reference",
            ]
        )

    assert count > 0


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ([date(2016, 8, 4), date(2016, 8, 30)], {}),
        (["2016-08-04", "2016-08-30"], {}),
    ],
)
def test_transactions(client_decimal, args, kwargs):
    info, transactions = client_decimal.transactions(*args, **kwargs)
    transaction = next(transactions)
    assert transaction["amount"] == Decimal("-130.0")
    assert info["balance"] == Decimal("2060.52")


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ([], {"from_id": 308}),
        ([], {"from_date": date(2016, 8, 4)}),
        ([], {"from_date": "2016-08-04"}),
    ],
)
def test_last_transactions(client_decimal, args, kwargs):
    info, transactions = client_decimal.last_transactions(*args, **kwargs)
    transaction = next(transactions)
    assert transaction["amount"] == Decimal("-130.0")
    assert info["balance"] == Decimal("2060.52")


def test_period_coerces_date(transactions_json):
    client = FioBank("...")

    from_date = "2016-08-04T09:36:42"
    to_date = "2016-08-30T11:45:38"

    options = {"return_value": transactions_json}
    with mock.patch.object(client, "_request", **options) as stub:
        client.period(from_date, to_date)
        stub.assert_called_once_with(
            "periods", from_date=date(2016, 8, 4), to_date=date(2016, 8, 30)
        )


def test_statement(transactions_json):
    client = FioBank("...")

    options = {"return_value": transactions_json}
    with mock.patch.object(client, "_request", **options) as stub:
        client.statement(2016, 308)
        stub.assert_called_once_with("by-id", year=2016, number=308)


def test_last_conflicting_params():
    client = FioBank("...")
    with pytest.raises(ValueError):
        client.last(from_id=308, from_date=date(2016, 8, 30))


def test_last_from_id(transactions_json):
    client = FioBank("...")

    options = {"return_value": transactions_json}
    with mock.patch.object(client, "_request", **options) as stub:
        client.last(from_id=308)
        stub.assert_has_calls(
            [
                mock.call("set-last-id", from_id=308),
                mock.call("last"),
            ]
        )


@pytest.mark.parametrize("test_input", [date(2016, 8, 30), "2016-08-30"])
def test_last_from_date(transactions_json, test_input):
    client = FioBank("...")

    options = {"return_value": transactions_json}
    with mock.patch.object(client, "_request", **options) as stub:
        client.last(from_date=test_input)
        stub.assert_has_calls(
            [
                mock.call("set-last-date", from_date=date(2016, 8, 30)),
                mock.call("last"),
            ]
        )


def test_transaction_schema_is_complete():
    # Skip test if running in Copilot environment (network restrictions)
    if os.environ.get("COPILOT_API_URL"):
        pytest.skip("Skipping network-dependent test in Copilot environment")

    response = requests.get("http://www.fio.cz/xsd/IBSchema.xsd")
    response.raise_for_status()
    xsd_text = response.text

    columns_in_xsd = set()

    element_re = re.compile(r'<\w+:element[^>]+name="column_(\d+)')
    for match in element_re.finditer(xsd_text):
        column_name = f"column{match.group(1)}"
        columns_in_xsd.add(column_name)

    # Get the column mappings from the Transaction model instead of transaction_schema
    from fiobank.models import Transaction

    transaction_aliases = set()
    for field_info in Transaction.model_fields.values():
        if field_info.alias:
            transaction_aliases.add(field_info.alias)

    assert frozenset(transaction_aliases) == columns_in_xsd


@pytest.mark.parametrize(
    "api_key, sdk_key, sdk_type",
    [
        # Generate test parameters from Transaction model fields with correct types
        ("column0", "date", lambda x: coerce_date(x)),
        ("column1", "amount", lambda x: float(x)),  # Use float as default
        ("column2", "account_number", str),
        ("column3", "bank_code", str),
        ("column4", "constant_symbol", str),
        ("column5", "variable_symbol", str),
        ("column6", "specific_symbol", str),
        ("column7", "user_identification", str),
        ("column8", "type", str),
        ("column9", "executor", str),
        ("column10", "account_name", str),
        ("column12", "bank_name", str),
        ("column14", "currency", str),
        ("column16", "recipient_message", str),
        ("column17", "instruction_id", str),
        ("column18", "specification", str),
        ("column22", "transaction_id", str),
        ("column25", "comment", str),
        ("column26", "bic", str),
        ("column27", "reference", str),
    ],
)
def test_transactions_parse(transactions_json, api_key, sdk_key, sdk_type):
    client = FioBank("...")

    api_transactions = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ]  # NOQA

    # The 'transactions.json' file is based on real data, so it doesn't
    # contain some values. To test all values, we use dummy data here.
    dummy_mapping = {"column0": "2015-08-30"}
    dummy_default = 30.8
    for api_transaction in api_transactions:
        dummy_value = dummy_mapping.get(api_key, dummy_default)
        api_transaction[api_key] = {"value": dummy_value}

    sdk_transactions = list(client._parse_transactions(transactions_json))
    assert len(sdk_transactions) == len(api_transactions)

    for i in range(len(api_transactions)):
        api_transaction = api_transactions[i]
        sdk_transaction = sdk_transactions[i]

        assert sdk_transaction[sdk_key] == sdk_type(api_transaction[api_key]["value"])


def test_transactions_parse_unsanitized(transactions_json):
    client = FioBank("...")

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    api_transaction["column10"] = {"value": "             Honza\n"}

    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert sdk_transaction["account_name"] == "Honza"


def test_transactions_parse_convert(transactions_json):
    client = FioBank("...")

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    api_transaction["column0"] = {"value": "2015-08-30"}

    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert sdk_transaction["date"] == date(2015, 8, 30)


def test_transactions_parse_none(transactions_json):
    client = FioBank("...")

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert api_transaction["column10"] is None
    assert sdk_transaction["account_name"] is None


def test_transactions_parse_missing(transactions_json):
    client = FioBank("...")

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    del api_transaction["column10"]

    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert "column10" not in api_transaction
    assert sdk_transaction["account_name"] is None


@pytest.mark.parametrize(
    "test_input",
    [
        "650.00 HRK",
        "-308 EUR",
        "46052.01 HUF",
    ],
)
def test_amount_re(test_input):
    assert FioBank._amount_re.match(test_input)


@pytest.mark.parametrize(
    "test_input, amount, currency",
    [
        ("650.00 HRK", 650.0, "HRK"),
        ("-308 EUR", -308.0, "EUR"),
        ("46052.01 HUF", 46052.01, "HUF"),
    ],
)
def test_transactions_parse_amount_as_float(
    transactions_json, test_input, amount, currency
):
    client = FioBank("...")

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    api_transaction["column18"] = {"value": test_input}

    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert sdk_transaction["specification"] == test_input
    assert sdk_transaction["original_amount"] == amount
    assert sdk_transaction["original_currency"] == currency


@pytest.mark.parametrize(
    "test_input, amount, currency",
    [
        ("650.00 HRK", Decimal("650.0"), "HRK"),
        ("-308 EUR", Decimal("-308.0"), "EUR"),
        ("46052.01 HUF", Decimal("46052.01"), "HUF"),
    ],
)
def test_transactions_parse_amount_as_decimal(
    transactions_json, test_input, amount, currency
):
    client = FioBank("...", decimal=True)

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    api_transaction["column18"] = {"value": test_input}

    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert sdk_transaction["specification"] == test_input
    assert sdk_transaction["original_amount"] == amount
    assert sdk_transaction["original_currency"] == currency


def test_transactions_parse_account_number_full(transactions_json):
    client = FioBank("...")

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    api_transaction["column2"] = {"value": 10000000002}
    api_transaction["column3"] = {"value": "2010"}

    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert sdk_transaction["account_number_full"] == "10000000002/2010"


def test_transactions_parse_no_account_number_full(transactions_json):
    client = FioBank("...")

    api_transaction = transactions_json["accountStatement"]["transactionList"][
        "transaction"
    ][0]  # NOQA
    api_transaction["column2"] = {"value": 10000000002}
    api_transaction["column3"] = {"value": None}

    sdk_transaction = next(client._parse_transactions(transactions_json))

    assert sdk_transaction["account_number_full"] is None


def test_409_conflict(token: str, transactions_text: str):
    with responses.RequestsMock(registry=OrderedRegistry) as resps:
        url = re.compile(
            re.escape(FioBank.base_url) + rf"[^/]+/{token}/([^/]+/)*transactions\.json"
        )
        resps.add(responses.GET, url, status=409)
        resps.add(responses.GET, url, body=transactions_text)
        client = FioBank(token, decimal=True)
        transaction = next(client.last())

    assert transaction["amount"] == Decimal("-130.0")
