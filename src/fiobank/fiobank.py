from __future__ import annotations

import json
import re
import warnings
from collections.abc import Generator
from datetime import date, datetime
from decimal import Decimal

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from .exceptions import HTTPError, ThrottlingError
from .models import Info, Transaction
from .transports import (
    AsyncTransport,
    HTTPXAsyncTransport,
    HTTPXTransport,
    Response,
    Transport,
)
from .utils import coerce_date


DEFAULT_BASE_URL = "https://fioapi.fio.cz/v1/rest/"


class FioBankBase:
    """Transport-agnostic core shared by :class:`FioBank` and
    :class:`AsyncFioBank`.

    It knows how to build URLs, interpret HTTP responses, sanitize the token
    out of error messages, decode JSON, and turn Fio's payloads into plain
    dictionaries. None of that touches the network, so both the synchronous
    and asynchronous clients reuse it unchanged.
    """

    _actions = {
        "periods": "periods/{token}/{from_date}/{to_date}/transactions.json",
        "by-id": "by-id/{token}/{year}/{number}/transactions.json",
        "last": "last/{token}/transactions.json",
        "set-last-id": "set-last-id/{token}/{from_id}/",
        "set-last-date": "set-last-date/{token}/{from_date}/",
        "last-statement": "lastStatement/{token}/statement",
    }

    _amount_re = re.compile(r"\-?\d+(\.\d+)? [A-Z]{3}")

    def __init__(
        self,
        token: str,
        *,
        decimal: bool = False,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: float = 60,
    ):
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Token cannot be None or empty")
        self.token = token.strip()

        self.base_url = base_url
        self.request_timeout = request_timeout

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

    def _build_url(self, action: str, **params) -> str:
        url_template = self.base_url + self._actions[action]
        return url_template.format(token=self.token, **params)

    def _sanitize(self, text: str) -> str:
        return text.replace(self.token, "***TOKEN***")

    def _check(self, url: str, response: Response) -> None:
        if response.status_code == 409:
            raise ThrottlingError()
        if response.status_code >= 400:
            message = f"HTTP {response.status_code} for {url}"
            try:
                body = response.text
            except UnicodeDecodeError:
                # An intermediary (gateway, proxy, WAF) may return a non-UTF-8
                # error body. Fall back to a lossy decode so the diagnostic
                # survives instead of masking the HTTPError with a decode crash.
                body = response.content.decode("utf-8", "replace")
            if body:
                message = f"{message}. Response body: {body}"
            raise HTTPError(self._sanitize(message), status_code=response.status_code)

    def _parse_json(self, response: Response) -> dict | None:
        if response.content:
            return json.loads(response.text, parse_float=self.float_type)
        return None

    def _parse_statement_number(self, response: Response) -> tuple[int, int] | None:
        year_value, _, number_value = response.text.strip().partition(",")
        if year_value == "null" or not number_value:
            return None
        return (int(year_value), int(number_value))

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


class FioBank(FioBankBase):
    def __init__(
        self,
        token: str,
        *,
        decimal: bool = False,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: float = 60,
        transport: Transport | None = None,
    ):
        super().__init__(
            token,
            decimal=decimal,
            base_url=base_url,
            request_timeout=request_timeout,
        )
        self.transport: Transport = transport or HTTPXTransport(timeout=request_timeout)

    @retry(
        retry=retry_if_exception_type(ThrottlingError),
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(max=2 * 60),
    )
    def _request(self, url: str, params: dict | None = None) -> Response:
        response = self.transport.get(url, params)
        self._check(url, response)
        return response

    def _request_json(self, action: str, **params) -> dict | None:
        url = self._build_url(action, **params)
        return self._parse_json(self._request(url))

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
        url = self._build_url("last-statement")
        params = {"year": year} if year is not None else None
        response = self._request(url, params=params)
        return self._parse_statement_number(response)

    def last_statement(self, year: int | None = None) -> Generator[dict]:
        if numbering := self._last_statement_number(year):
            return self.statement(*numbering)
        raise ValueError("No data available")

    def close(self) -> None:
        """Release the transport (and its default HTTP client, if any).

        A no-op for custom transports that don't expose ``close()``.
        """
        close = getattr(self.transport, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> FioBank:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


class AsyncFioBank(FioBankBase):
    def __init__(
        self,
        token: str,
        *,
        decimal: bool = False,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: float = 60,
        transport: AsyncTransport | None = None,
    ):
        super().__init__(
            token,
            decimal=decimal,
            base_url=base_url,
            request_timeout=request_timeout,
        )
        self.transport: AsyncTransport = transport or HTTPXAsyncTransport(
            timeout=request_timeout
        )

    @retry(
        retry=retry_if_exception_type(ThrottlingError),
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(max=2 * 60),
    )
    async def _request(self, url: str, params: dict | None = None) -> Response:
        # tenacity detects the coroutine and retries it with AsyncRetrying.
        response = await self.transport.get(url, params)
        self._check(url, response)
        return response

    async def _request_json(self, action: str, **params) -> dict | None:
        url = self._build_url(action, **params)
        return self._parse_json(await self._request(url))

    async def info(self) -> dict:
        today = date.today()
        if data := await self._request_json("periods", from_date=today, to_date=today):
            return self._parse_info(data)
        raise ValueError("No data available")

    async def _fetch_period(
        self, from_date: str | date | datetime, to_date: str | date | datetime
    ) -> dict:
        if data := await self._request_json(
            "periods", from_date=coerce_date(from_date), to_date=coerce_date(to_date)
        ):
            return data
        raise ValueError("No data available")

    async def period(
        self, from_date: str | date | datetime, to_date: str | date | datetime
    ) -> Generator[dict]:
        data = await self._fetch_period(from_date, to_date)
        return self._parse_transactions(data)

    async def transactions(
        self, from_date: str | date | datetime, to_date: str | date | datetime
    ) -> tuple[dict, Generator[dict]]:
        if data := await self._fetch_period(from_date, to_date):
            return (self._parse_info(data), self._parse_transactions(data))
        raise ValueError("No data available")

    async def statement(self, year: int, number: int) -> Generator[dict]:
        if data := await self._request_json("by-id", year=year, number=number):
            return self._parse_transactions(data)
        raise ValueError("No data available")

    async def _fetch_last(
        self, from_id: str | None = None, from_date: str | date | datetime | None = None
    ) -> dict:
        if from_id and from_date:
            raise ValueError("Only one constraint is allowed.")

        if from_id:
            await self._request_json("set-last-id", from_id=from_id)
        elif from_date:
            await self._request_json("set-last-date", from_date=coerce_date(from_date))

        if data := await self._request_json("last"):
            return data
        raise ValueError("No data available")

    async def last(
        self, from_id: str | None = None, from_date: str | date | datetime | None = None
    ) -> Generator[dict]:
        return self._parse_transactions(await self._fetch_last(from_id, from_date))

    async def last_transactions(
        self, from_id: str | None = None, from_date: str | date | datetime | None = None
    ) -> tuple[dict, Generator[dict]]:
        data = await self._fetch_last(from_id, from_date)
        return (self._parse_info(data), self._parse_transactions(data))

    async def _last_statement_number(
        self, year: int | None = None
    ) -> tuple[int, int] | None:
        url = self._build_url("last-statement")
        params = {"year": year} if year is not None else None
        response = await self._request(url, params=params)
        return self._parse_statement_number(response)

    async def last_statement(self, year: int | None = None) -> Generator[dict]:
        if numbering := await self._last_statement_number(year):
            return await self.statement(*numbering)
        raise ValueError("No data available")

    async def aclose(self) -> None:
        """Release the transport (and its default HTTP client, if any).

        A no-op for custom transports that don't expose ``aclose()``.
        """
        aclose = getattr(self.transport, "aclose", None)
        if callable(aclose):
            await aclose()

    async def __aenter__(self) -> AsyncFioBank:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()
