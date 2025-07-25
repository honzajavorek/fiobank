from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Union

from pydantic import BaseModel, Field, field_validator

from .utils import coerce_date, sanitize_value


class Transaction(BaseModel):
    """Pydantic model for bank transaction data."""
    
    date: date | None = Field(None, alias="column0")
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
    
    # Additional computed fields
    account_number_full: str | None = None
    original_amount: float | Decimal | None = None
    original_currency: str | None = None
    
    model_config = {"populate_by_name": True}

    @staticmethod
    def _extract_value(v: Any) -> Any:
        """Extract value from API format {"name": "...", "value": "...", "id": ...} or return None."""
        if v is None:
            return None
        if isinstance(v, dict) and "value" in v:
            return v["value"]
        return v
    
    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, v: Any) -> date | None:
        v = cls._extract_value(v)
        v = sanitize_value(v)
        if v is not None:
            return coerce_date(v)
        return None
    
    @field_validator('amount', mode='before')
    @classmethod
    def parse_amount(cls, v: Any, info) -> float | Decimal | None:
        v = cls._extract_value(v)
        v = sanitize_value(v)
        if v is not None:
            # Get the float_type from the context or use float as default
            float_type = info.context.get('float_type', float) if info.context else float
            return float_type(v)
        return None
    
    @field_validator(
        'account_number', 'bank_code', 'constant_symbol', 'variable_symbol',
        'specific_symbol', 'user_identification', 'type', 'executor',
        'account_name', 'bank_name', 'currency', 'recipient_message',
        'instruction_id', 'specification', 'transaction_id', 'comment',
        'bic', 'reference', mode='before'
    )
    @classmethod
    def parse_string_field(cls, v: Any) -> str | None:
        v = cls._extract_value(v)
        return sanitize_value(v, str)


class Info(BaseModel):
    """Pydantic model for account information."""
    
    account_number: str | None = Field(None, alias="accountId")
    bank_code: str | None = Field(None, alias="bankId") 
    currency: str | None = Field(None, alias="currency")
    iban: str | None = Field(None, alias="iban")
    bic: str | None = Field(None, alias="bic")
    balance: float | Decimal | None = Field(None, alias="closingBalance")
    
    # Additional computed field
    account_number_full: str | None = None
    
    model_config = {"populate_by_name": True}
    
    @field_validator('balance', mode='before')
    @classmethod
    def parse_balance(cls, v: Any, info) -> float | Decimal | None:
        v = sanitize_value(v)
        if v is not None:
            # Get the float_type from the context or use float as default
            float_type = info.context.get('float_type', float) if info.context else float
            return float_type(v)
        return None
    
    @field_validator(
        'account_number', 'bank_code', 'currency', 'iban', 'bic', mode='before'
    )
    @classmethod
    def parse_string_field(cls, v: Any) -> str | None:
        return sanitize_value(v, str)