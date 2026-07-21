from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .utils import coerce_date, sanitize_value


def money_type(info: ValidationInfo) -> type:
    """Whether to represent monetary values as ``float`` or ``Decimal``.

    Controlled by the client through the validation context, see
    ``FioBank(..., decimal=True)``.
    """
    if info.context:
        return info.context.get("money_type", float)
    return float


class Transaction(BaseModel):
    """A single transaction as returned by the Fio API.

    The API represents each field as a ``column<N>`` object with a ``value``
    key (or ``null`` when empty), see http://www.fio.cz/xsd/IBSchema.xsd
    """

    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)

    date: datetime.date | None = Field(None, alias="column0")
    amount: float | Decimal | None = Field(None, alias="column1")
    account_number: str | None = Field(None, alias="column2")
    bank_code: str | None = Field(None, alias="column3")
    constant_symbol: str | None = Field(None, alias="column4")
    variable_symbol: str | None = Field(None, alias="column5")
    specific_symbol: str | None = Field(None, alias="column6")
    user_identification: str | None = Field(None, alias="column7")
    type: str | None = Field(None, alias="column8")
    executor: str | None = Field(None, alias="column9")
    account_name: str | None = Field(None, alias="column10")
    bank_name: str | None = Field(None, alias="column12")
    currency: str | None = Field(None, alias="column14")
    recipient_message: str | None = Field(None, alias="column16")
    instruction_id: str | None = Field(None, alias="column17")
    specification: str | None = Field(None, alias="column18")
    transaction_id: str | None = Field(None, alias="column22")
    comment: str | None = Field(None, alias="column25")
    bic: str | None = Field(None, alias="column26")
    reference: str | None = Field(None, alias="column27")

    @model_validator(mode="before")
    @classmethod
    def _unwrap_columns(cls, data: dict) -> dict:
        return {
            key.lower(): sanitize_value(column.get("value"))
            for key, column in data.items()
            if isinstance(column, dict)
        }

    @field_validator("date", mode="before")
    @classmethod
    def _coerce_date(cls, value):
        return coerce_date(value) if value is not None else None

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, value, info: ValidationInfo):
        return money_type(info)(value) if value is not None else None


class Info(BaseModel):
    """Account information as returned by the Fio API."""

    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)

    account_number: str | None = Field(None, alias="accountid")
    bank_code: str | None = Field(None, alias="bankid")
    currency: str | None = Field(None, alias="currency")
    iban: str | None = Field(None, alias="iban")
    bic: str | None = Field(None, alias="bic")
    balance: float | Decimal | None = Field(None, alias="closingbalance")

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: dict) -> dict:
        # The API is inconsistent about the casing of the keys, so we
        # lower-case them to match them against the (lower-cased) aliases.
        return {key.lower(): sanitize_value(value) for key, value in data.items()}

    @field_validator("balance", mode="before")
    @classmethod
    def _coerce_balance(cls, value, info: ValidationInfo):
        return money_type(info)(value) if value is not None else None
