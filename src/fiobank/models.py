import datetime
from decimal import Decimal
from typing import Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .utils import coerce_date, sanitize_value


Money = Optional[Union[float, Decimal]]


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

    date: Optional[datetime.date] = Field(None, alias="column0")
    amount: Money = Field(None, alias="column1")
    account_number: Optional[str] = Field(None, alias="column2")
    bank_code: Optional[str] = Field(None, alias="column3")
    constant_symbol: Optional[str] = Field(None, alias="column4")
    variable_symbol: Optional[str] = Field(None, alias="column5")
    specific_symbol: Optional[str] = Field(None, alias="column6")
    user_identification: Optional[str] = Field(None, alias="column7")
    type: Optional[str] = Field(None, alias="column8")
    executor: Optional[str] = Field(None, alias="column9")
    account_name: Optional[str] = Field(None, alias="column10")
    bank_name: Optional[str] = Field(None, alias="column12")
    currency: Optional[str] = Field(None, alias="column14")
    recipient_message: Optional[str] = Field(None, alias="column16")
    instruction_id: Optional[str] = Field(None, alias="column17")
    specification: Optional[str] = Field(None, alias="column18")
    transaction_id: Optional[str] = Field(None, alias="column22")
    comment: Optional[str] = Field(None, alias="column25")
    bic: Optional[str] = Field(None, alias="column26")
    reference: Optional[str] = Field(None, alias="column27")

    @model_validator(mode="before")
    @classmethod
    def _unwrap_columns(cls, data: dict) -> dict:
        return {
            key: sanitize_value(column.get("value"))
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

    account_number: Optional[str] = Field(None, alias="accountId")
    bank_code: Optional[str] = Field(None, alias="bankId")
    currency: Optional[str] = Field(None, alias="currency")
    iban: Optional[str] = Field(None, alias="iban")
    bic: Optional[str] = Field(None, alias="bic")
    balance: Money = Field(None, alias="closingBalance")

    @field_validator("balance", mode="before")
    @classmethod
    def _coerce_balance(cls, value, info: ValidationInfo):
        return money_type(info)(value) if value is not None else None
