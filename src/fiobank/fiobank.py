from __future__ import annotations

import re
import warnings
from collections.abc import Generator
from datetime import date, datetime
from decimal import Decimal

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from .exceptions import ThrottlingError
from .models import Info, Transaction
from .utils import coerce_date, sanitize_value


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

    @property
    def transaction_schema(self) -> dict:
        """Legacy transaction schema property (deprecated).
        
        This property provides access to the old transaction schema mapping
        but is deprecated and will be removed in a future version.
        Use the new Pydantic models instead.
        """
        import warnings
        warnings.warn(
            "transaction_schema is deprecated and will be removed in a future version. "
            "Use the new Pydantic models instead.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError(
            "transaction_schema has been replaced with Pydantic models. "
            "This property is no longer supported."
        )

    @retry(
        retry=retry_if_exception_type(ThrottlingError),
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(max=2 * 60),
    )
    def _request(self, action: str, **params) -> dict | None:
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
        # parse data from API using Pydantic model
        raw_info = data["accountStatement"]["info"]
        
        # Handle case-insensitive field names
        normalized_info = {}
        field_mappings = {
            "accountid": "accountId",
            "bankid": "bankId", 
            "currency": "currency",
            "iban": "iban",
            "bic": "bic",
            "closingbalance": "closingBalance"
        }
        
        for key, value in raw_info.items():
            key_lower = key.lower()
            normalized_key = field_mappings.get(key_lower, key)
            normalized_info[normalized_key] = value
        
        info_model = Info.model_validate(
            normalized_info, 
            context={"float_type": self.float_type}
        )
        info = info_model.model_dump(by_alias=False, exclude_none=False)

        # make some refinements
        self._add_account_number_full(info)

        # return data
        return info

    def _parse_transactions(self, data: dict) -> Generator[dict, None, None]:
        try:
            entries = data["accountStatement"]["transactionList"]["transaction"]
        except TypeError:
            entries = []

        for entry in entries:
            # parse entry from API using Pydantic model
            transaction_model = Transaction.model_validate(
                entry, 
                context={"float_type": self.float_type}
            )
            trans = transaction_model.model_dump(by_alias=False, exclude_none=False)

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
        if data := self._request(
            "periods", from_date=coerce_date(from_date), to_date=coerce_date(to_date)
        ):
            return data
        raise ValueError("No data available")

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

    def statement(self, year: int, number: int) -> Generator[dict]:
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
