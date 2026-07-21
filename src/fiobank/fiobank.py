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
from .utils import coerce_date


class FioBank:
    base_url = "https://fioapi.fio.cz/v1/rest/"

    # Seconds to wait for the API before giving up, so an unresponsive
    # server can't hang the caller indefinitely.
    request_timeout = 60

    actions = {
        "periods": "periods/{token}/{from_date}/{to_date}/transactions.json",
        "by-id": "by-id/{token}/{year}/{number}/transactions.json",
        "last": "last/{token}/transactions.json",
        "set-last-id": "set-last-id/{token}/{from_id}/",
        "set-last-date": "set-last-date/{token}/{from_date}/",
        "last-statement": "lastStatement/{token}/statement",
    }

    _amount_re = re.compile(r"\-?\d+(\.\d+)? [A-Z]{3}")

    def __init__(self, token: str, *, decimal: bool = False):
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Token cannot be None or empty")
        self.token = token.strip()

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
    def transaction_schema(self) -> None:
        raise NotImplementedError(
            "'transaction_schema' has been removed. It was never a public "
            "part of the API. Transactions are now parsed with the "
            "'fiobank.models.Transaction' Pydantic model."
        )

    @property
    def info_schema(self) -> None:
        raise NotImplementedError(
            "'info_schema' has been removed. It was never a public part of "
            "the API. Account info is now parsed with the "
            "'fiobank.models.Info' Pydantic model."
        )

    @retry(
        retry=retry_if_exception_type(ThrottlingError),
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(max=2 * 60),
    )
    def _request(self, url: str, params: dict | None = None) -> requests.Response:
        response = requests.get(url, params=params, timeout=self.request_timeout)
        if response.status_code == requests.codes["conflict"]:
            raise ThrottlingError()

        # Handle all other HTTP errors with token sanitization and response body
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # Get the original error message and sanitize token
            sanitized_msg = str(e).replace(self.token, "***TOKEN***")

            # Try to get response body and sanitize it too
            try:
                response_body = response.text
                if response_body:
                    # Sanitize token from response body as well
                    sanitized_body = response_body.replace(self.token, "***TOKEN***")
                    # Append response body to the error message
                    sanitized_msg = f"{sanitized_msg}. Response body: {sanitized_body}"
            except Exception:
                pass  # If we can't get response body, just use the original error

            raise requests.HTTPError(sanitized_msg, response=response)

        return response

    def _request_json(self, action: str, **params) -> dict | None:
        url_template = self.base_url + self.actions[action]
        url = url_template.format(token=self.token, **params)

        response = self._request(url)
        if response.content:
            return response.json(parse_float=self.float_type)
        return None

    def _parse_info(self, data: dict) -> dict:
        info = Info.model_validate(
            data["accountStatement"]["info"], context={"money_type": self.float_type}
        ).model_dump()

        # make some refinements
        self._add_account_number_full(info)

        return info

    def _parse_transactions(self, data: dict) -> Generator[dict, None, None]:
        try:
            entries = data["accountStatement"]["transactionList"]["transaction"]
        except TypeError:
            entries = []

        for entry in entries:
            trans = Transaction.model_validate(
                entry, context={"money_type": self.float_type}
            ).model_dump()

            # make some refinements
            specification = trans["specification"]
            if specification is not None and self._amount_re.fullmatch(specification):
                amount, currency = specification.split(" ")
                trans["original_amount"] = self.float_type(amount)
                trans["original_currency"] = currency
            else:
                trans["original_amount"] = None
                trans["original_currency"] = None

            self._add_account_number_full(trans)

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
        if data := self._request_json("periods", from_date=today, to_date=today):
            return self._parse_info(data)
        raise ValueError("No data available")

    def _fetch_period(
        self, from_date: str | date | datetime, to_date: str | date | datetime
    ) -> dict:
        if data := self._request_json(
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
        if data := self._request_json("by-id", year=year, number=number):
            return self._parse_transactions(data)
        raise ValueError("No data available")

    def _fetch_last(
        self, from_id: str | None = None, from_date: str | date | datetime | None = None
    ) -> dict:
        if from_id and from_date:
            raise ValueError("Only one constraint is allowed.")

        if from_id:
            self._request_json("set-last-id", from_id=from_id)
        elif from_date:
            self._request_json("set-last-date", from_date=coerce_date(from_date))

        if data := self._request_json("last"):
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

    def _last_statement_number(self, year: int | None = None) -> tuple[int, int] | None:
        url = self.base_url + self.actions["last-statement"].format(token=self.token)
        params = {"year": year} if year is not None else None

        response = self._request(url, params=params)
        year_value, _, number_value = response.text.strip().partition(",")
        if year_value == "null" or not number_value:
            return None
        return (int(year_value), int(number_value))

    def last_statement(self, year: int | None = None) -> Generator[dict]:
        if numbering := self._last_statement_number(year):
            return self.statement(*numbering)
        raise ValueError("No data available")
