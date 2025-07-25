from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Union

try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Create minimal mock classes for testing
    class BaseModel:
        model_config = {}
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        
        @classmethod
        def model_validate(cls, data, context=None):
            instance = cls()
            # Get all field aliases and their mappings
            field_mappings = {}
            for attr in dir(cls):
                if attr.startswith('_') or callable(getattr(cls, attr)):
                    continue
                field_obj = getattr(cls, attr)
                if hasattr(field_obj, 'alias') and field_obj.alias:
                    field_mappings[field_obj.alias] = attr
                else:
                    field_mappings[attr] = attr
            
            # Process each field
            for key, value in data.items():
                field_name = field_mappings.get(key)
                if field_name:
                    # Apply validator if available
                    validator_method_name = f'parse_{field_name}'
                    if hasattr(cls, validator_method_name):
                        validator = getattr(cls, validator_method_name)
                        try:
                            # Mock info object
                            class MockInfo:
                                def __init__(self, context):
                                    self.context = context or {}
                            value = validator(value, MockInfo(context))
                        except TypeError:
                            # Validator doesn't take info parameter
                            value = validator(value)
                    setattr(instance, field_name, value)
            
            # Set None for missing fields
            for attr in dir(cls):
                if not attr.startswith('_') and not callable(getattr(cls, attr)):
                    if not hasattr(instance, attr):
                        setattr(instance, attr, None)
            
            return instance
        
        def model_dump(self, by_alias=False, exclude_none=False):
            result = {}
            for attr in dir(self):
                if attr.startswith('_') or attr.startswith('model_') or callable(getattr(self, attr)):
                    continue
                value = getattr(self, attr)
                if exclude_none and value is None:
                    continue
                result[attr] = value
            return result
    
    class MockField:
        def __init__(self, default=None, alias=None):
            self.default = default
            self.alias = alias
    
    Field = MockField
    
    def field_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from .utils import coerce_date, sanitize_value


class Transaction(BaseModel):
    """Pydantic model for bank transaction data."""
    
    date = Field(None, alias="column0")
    amount = Field(None, alias="column1")
    account_number = Field(None, alias="column2")
    bank_code = Field(None, alias="column3")
    constant_symbol = Field(None, alias="column4")
    variable_symbol = Field(None, alias="column5")
    specific_symbol = Field(None, alias="column6")
    user_identification = Field(None, alias="column7")
    type = Field(None, alias="column8")
    executor = Field(None, alias="column9")
    account_name = Field(None, alias="column10")
    bank_name = Field(None, alias="column12")
    currency = Field(None, alias="column14")
    recipient_message = Field(None, alias="column16")
    instruction_id = Field(None, alias="column17")
    specification = Field(None, alias="column18")
    transaction_id = Field(None, alias="column22")
    comment = Field(None, alias="column25")
    bic = Field(None, alias="column26")
    reference = Field(None, alias="column27")
    
    # Additional computed fields
    account_number_full = None
    original_amount = None
    original_currency = None
    
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
    def parse_amount(cls, v: Any, info=None) -> float | Decimal | None:
        v = cls._extract_value(v)
        v = sanitize_value(v)
        if v is not None:
            # Get the float_type from the context or use float as default
            float_type = info.context.get('float_type', float) if info and hasattr(info, 'context') else float
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
    
    account_number = Field(None, alias="accountId")
    bank_code = Field(None, alias="bankId") 
    currency = Field(None, alias="currency")
    iban = Field(None, alias="iban")
    bic = Field(None, alias="bic")
    balance = Field(None, alias="closingBalance")
    
    # Additional computed field
    account_number_full = None
    
    model_config = {"populate_by_name": True}
    
    @field_validator('balance', mode='before')
    @classmethod
    def parse_balance(cls, v: Any, info=None) -> float | Decimal | None:
        v = sanitize_value(v)
        if v is not None:
            # Get the float_type from the context or use float as default
            float_type = info.context.get('float_type', float) if info and hasattr(info, 'context') else float
            return float_type(v)
        return None
    
    @field_validator(
        'account_number', 'bank_code', 'currency', 'iban', 'bic', mode='before'
    )
    @classmethod
    def parse_string_field(cls, v: Any) -> str | None:
        return sanitize_value(v, str)