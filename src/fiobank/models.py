from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Optional, Union

try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    PYDANTIC_AVAILABLE = False
    
    # Create minimal mock classes for fallback when pydantic is not available
    class BaseModel:
        model_config = {}
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        
        @classmethod
        def model_validate(cls, data, context=None):
            instance = cls()
            
            # Define which fields use which validators (simulating the @field_validator decorator)
            validator_mappings = {
                'date': 'parse_date',
                'amount': 'parse_amount',
                # All string fields use parse_string_field
                'account_number': 'parse_string_field',
                'bank_code': 'parse_string_field', 
                'constant_symbol': 'parse_string_field',
                'variable_symbol': 'parse_string_field',
                'specific_symbol': 'parse_string_field',
                'user_identification': 'parse_string_field',
                'type': 'parse_string_field',
                'executor': 'parse_string_field',
                'account_name': 'parse_string_field',
                'bank_name': 'parse_string_field',
                'currency': 'parse_string_field',
                'recipient_message': 'parse_string_field',
                'instruction_id': 'parse_string_field',
                'specification': 'parse_string_field',
                'transaction_id': 'parse_string_field',
                'comment': 'parse_string_field',
                'bic': 'parse_string_field',
                'reference': 'parse_string_field',
                # Info model fields
                'balance': 'parse_balance',
            }
            
            # Get all field aliases and their mappings  
            field_mappings = {}
            for attr in dir(cls):
                if attr.startswith('_') or callable(getattr(cls, attr)):
                    continue
                field_obj = getattr(cls, attr)
                if hasattr(field_obj, 'alias') and field_obj.alias:
                    field_mappings[field_obj.alias] = attr
                
            # Process each field from data
            for key, value in data.items():
                field_name = field_mappings.get(key)
                if field_name:
                    # Apply validator if available
                    validator_method_name = validator_mappings.get(field_name)
                    if validator_method_name and hasattr(cls, validator_method_name):
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
            
            # Set None for missing mapped fields
            for alias, field_name in field_mappings.items():
                if not hasattr(instance, field_name):
                    setattr(instance, field_name, None)
            
            return instance
        
        def model_dump(self, by_alias=False, exclude_none=False):
            result = {}
            for attr in dir(self):
                if attr.startswith('_') or attr.startswith('model_') or callable(getattr(self, attr)):
                    continue
                value = getattr(self, attr)
                # Skip MockField objects and convert them to None
                if hasattr(value, '__class__') and 'MockField' in str(value.__class__):
                    value = None
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
    
    date: Optional[date] = Field(None, alias="column0")
    amount: Union[float, Decimal, None] = Field(None, alias="column1")
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
    
    # Additional computed fields
    account_number_full: Optional[str] = Field(default=None)
    original_amount: Union[float, Decimal, None] = Field(default=None)
    original_currency: Optional[str] = Field(default=None)
    
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

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
    def parse_date(cls, v: Any) -> Optional[date]:
        v = cls._extract_value(v)
        v = sanitize_value(v)
        if v is not None:
            return coerce_date(v)
        return None
    
    @field_validator('amount', mode='before') 
    @classmethod
    def parse_amount(cls, v: Any, info) -> Union[float, Decimal, None]:
        v = cls._extract_value(v)
        v = sanitize_value(v)
        if v is not None:
            # Get the float_type from the context or use float as default
            float_type = float
            if info and hasattr(info, 'context') and info.context:
                float_type = info.context.get('float_type', float)
            
            # If we're converting to Decimal and the input is a float,
            # convert to string first to avoid precision issues
            if float_type == Decimal and isinstance(v, float):
                return Decimal(str(v))
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
    def parse_string_field(cls, v: Any) -> Optional[str]:
        v = cls._extract_value(v)
        return sanitize_value(v, str)


class Info(BaseModel):
    """Pydantic model for account information."""
    
    account_number: Optional[str] = Field(None, alias="accountId")
    bank_code: Optional[str] = Field(None, alias="bankId") 
    currency: Optional[str] = Field(None, alias="currency")
    iban: Optional[str] = Field(None, alias="iban")
    bic: Optional[str] = Field(None, alias="bic")
    balance: Union[float, Decimal, None] = Field(None, alias="closingBalance")
    
    # Additional computed field
    account_number_full: Optional[str] = Field(default=None)
    
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
    
    @field_validator('balance', mode='before')
    @classmethod
    def parse_balance(cls, v: Any, info) -> Union[float, Decimal, None]:
        v = sanitize_value(v)
        if v is not None:
            # Get the float_type from the context or use float as default
            float_type = float
            if info and hasattr(info, 'context') and info.context:
                float_type = info.context.get('float_type', float)
            
            # If we're converting to Decimal and the input is a float,
            # convert to string first to avoid precision issues
            if float_type == Decimal and isinstance(v, float):
                return Decimal(str(v))
            return float_type(v)
        return None
    
    @field_validator(
        'account_number', 'bank_code', 'currency', 'iban', 'bic', mode='before'
    )
    @classmethod
    def parse_string_field(cls, v: Any) -> Optional[str]:
        return sanitize_value(v, str)