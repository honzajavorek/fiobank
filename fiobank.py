from __future__ import annotations

import re
import warnings
from collections.abc import Generator
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)


__all__ = ("FioBank", "ThrottlingError")


def coerce_amount(value: "int | float") -> Decimal:
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    raise ValueError(value)


def coerce_date(value: "datetime | date | str") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def sanitize_value(value: Any, convert: "Callable | None" = None) -> Any:
    if isinstance(value, str):
        value = value.strip() or None
    if convert and value is not None:
        return convert(value)
    return value


class ThrottlingError(Exception):
    """Throttling error raised when the API is being used too fast."""

    def __str__(self) -> str:
        return "Token can be used only once per 30s"


class FioBank:
    base_url = "https://fioapi.fio.cz/v1/rest/"

    actions = {
        "periods": "periods/{token}/{from_date}/{to_date}/transactions.json",
        "by-id": "by-id/{token}/{year}/{number}/transactions.json",
        "last": "last/{token}/transactions.json",
        "set-last-id": "set-last-id/{token}/{from_id}/",
        "set-last-date": "set-last-date/{token}/{from_date}/",
    }

    _amount_re = re.compile(r"\-?\d+(\.\d+)? [A-Z]{3}")

    def __init__(self, token: str, *, decimal: bool = False):
        self.token = token

        if decimal:
            self.float_type = Decimal
        else:
            warnings.warn(
                (
                    "Using float for money can cause inaccuracies. "
                    "Use FioBank(..., decimal=True) for Decimal objects instead. "
                    "This will be the default in the future versions."
                ),
                DeprecationWarning,
            )
            self.float_type = float

        # http://www.fio.cz/xsd/IBSchema.xsd
        self.transaction_schema = {
            "column0": ("date", coerce_date),
            "column1": ("amount", self.float_type),
            "column2": ("account_number", str),
            "column3": ("bank_code", str),
            "column4": ("constant_symbol", str),
            "column5": ("variable_symbol", str),
            "column6": ("specific_symbol", str),
            "column7": ("user_identification", str),
            "column8": ("type", str),
            "column9": ("executor", str),
            "column10": ("account_name", str),
            "column12": ("bank_name", str),
            "column14": ("currency", str),
            "column16": ("recipient_message", str),
            "column17": ("instruction_id", str),
            "column18": ("specification", str),
            "column22": ("transaction_id", str),
            "column25": ("comment", str),
            "column26": ("bic", str),
            "column27": ("reference", str),
        }
        self.info_schema = {
            "accountid": ("account_number", str),
            "bankid": ("bank_code", str),
            "currency": ("currency", str),
            "iban": ("iban", str),
            "bic": ("bic", str),
            "closingbalance": ("balance", self.float_type),
        }

    @retry(
        retry=retry_if_exception_type(ThrottlingError),
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(max=2 * 60),
    )
    def _request(self, action: str, **params) -> "dict | None":
        url_template = self.base_url + self.actions[action]
        url = url_template.format(token=self.token, **params)

        response = requests.get(url)
        if response.status_code == requests.codes["conflict"]:
            raise ThrottlingError()
        response.raise_for_status()

        if response.content:
            return response.json(parse_float=self.float_type)
        return None

    def _parse_info(self, data: dict) -> dict:
        # parse data from API
        info = {}
        for key, value in data["accountStatement"]["info"].items():
            key = key.lower()
            if key in self.info_schema:
                field_name, convert = self.info_schema[key]
                value = sanitize_value(value, convert)
                info[field_name] = value

        # make some refinements
        self._add_account_number_full(info)

        # return data
        return info

    def _parse_transactions(self, data: dict) -> Generator[dict, None, None]:
        schema = self.transaction_schema
        try:
            entries = data["accountStatement"]["transactionList"]["transaction"]
        except TypeError:
            entries = []

        for entry in entries:
            # parse entry from API
            trans = {}
            for column_name, column_data in entry.items():
                if not column_data:
                    continue
                field_name, convert = schema[column_name.lower()]
                value = sanitize_value(column_data["value"], convert)
                trans[field_name] = value

            # add missing fileds with None values
            for column_data_name, (field_name, convert) in schema.items():
                trans.setdefault(field_name, None)

            # make some refinements
            specification = trans.get("specification")
            is_amount = self._amount_re.match
            if specification is not None and is_amount(specification):
                amount, currency = trans["specification"].split(" ")
                trans["original_amount"] = self.float_type(amount)
                trans["original_currency"] = currency
            else:
                trans["original_amount"] = None
                trans["original_currency"] = None

            self._add_account_number_full(trans)

            # generate transaction data
            yield trans

    def _add_account_number_full(self, obj: dict) -> None:
        account_number = obj.get("account_number")
        bank_code = obj.get("bank_code")

        if account_number is not None and bank_code is not None:
            account_number_full = f"{account_number}/{bank_code}"
        else:
            account_number_full = None

        obj["account_number_full"] = account_number_full

    def info(self) -> dict:
        today = date.today()
        if data := self._request("periods", from_date=today, to_date=today):
            return self._parse_info(data)
        raise ValueError("No data available")

    def _fetch_period(
        self, from_date: str | date | datetime, to_date: str | date | datetime
    ) -> dict:
        return self._request(
            "periods", from_date=coerce_date(from_date), to_date=coerce_date(to_date)
        )

    def period(
        self, from_date: str | date | datetime, to_date: str | date | datetime
    ) -> Generator[dict]:
        data = self._fetch_period(from_date, to_date)
        return self._parse_transactions(data)

    def transactions(
        self, from_date: str | date | datetime, to_date: str | date | datetime
    ) -> tuple[dict, Generator[dict]]:
        if data := self._fetch_period(from_date, to_date):
            return (self._parse_info(data), self._parse_transactions(data))
        raise ValueError("No data available")

    def statement(self, year, number):
        if data := self._request("by-id", year=year, number=number):
            return self._parse_transactions(data)
        raise ValueError("No data available")

    def _fetch_last(
        self, from_id: str | None = None, from_date: str | date | datetime | None = None
    ) -> dict:
        if from_id and from_date:
            raise ValueError("Only one constraint is allowed.")

        if from_id:
            self._request("set-last-id", from_id=from_id)
        elif from_date:
            self._request("set-last-date", from_date=coerce_date(from_date))

        if data := self._request("last"):
            return data
        raise ValueError("No data available")

    def last(
        self, from_id: str | None = None, from_date: str | date | datetime | None = None
    ) -> Generator[dict]:
        return self._parse_transactions(self._fetch_last(from_id, from_date))

    def last_transactions(
        self, from_id: str | None = None, from_date: str | date | datetime | None = None
    ) -> tuple[dict, Generator[dict]]:
        data = self._fetch_last(from_id, from_date)
        return (self._parse_info(data), self._parse_transactions(data))
