from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal

from fiobank import FioBank
from fiobank.models import Info, Transaction


def test_pydantic_models_with_float():
    """Test that pydantic models work correctly with float mode."""
    # Load test data
    test_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else 'tests'
    with open(os.path.join(test_dir, "transactions.json")) as f:
        data = json.load(f)
    
    # Test Info model
    info_data = data["accountStatement"]["info"]
    info_model = Info.model_validate(info_data, context={"float_type": float})
    info_dict = info_model.model_dump()
    
    assert info_dict["account_number"] == "1234567890"
    assert info_dict["bank_code"] == "2010"
    assert info_dict["currency"] == "CZK"
    assert isinstance(info_dict["balance"], float)
    assert info_dict["balance"] == 2060.52
    
    # Test Transaction model
    transaction_data = data["accountStatement"]["transactionList"]["transaction"][0]
    transaction_model = Transaction.model_validate(transaction_data, context={"float_type": float})
    transaction_dict = transaction_model.model_dump()
    
    assert transaction_dict["date"] == date(2016, 8, 3)
    assert isinstance(transaction_dict["amount"], float)
    assert transaction_dict["amount"] == -130.0
    assert transaction_dict["currency"] == "CZK"
    assert transaction_dict["type"] == "Platba kartou"


def test_pydantic_models_with_decimal():
    """Test that pydantic models work correctly with Decimal mode."""
    # Load test data
    test_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else 'tests'
    with open(os.path.join(test_dir, "transactions.json")) as f:
        data = json.load(f)
    
    # Test Info model
    info_data = data["accountStatement"]["info"]
    info_model = Info.model_validate(info_data, context={"float_type": Decimal})
    info_dict = info_model.model_dump()
    
    assert isinstance(info_dict["balance"], Decimal)
    
    # Test Transaction model  
    transaction_data = data["accountStatement"]["transactionList"]["transaction"][0]
    transaction_model = Transaction.model_validate(transaction_data, context={"float_type": Decimal})
    transaction_dict = transaction_model.model_dump()
    
    assert isinstance(transaction_dict["amount"], Decimal)
    assert transaction_dict["amount"] == Decimal("-130.0")


def test_fiobank_integration_float():
    """Test that FioBank integration works with float mode."""
    client = FioBank("test_token", decimal=False)
    
    # Load test data
    test_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else 'tests'
    with open(os.path.join(test_dir, "transactions.json")) as f:
        data = json.load(f)
    
    # Test info parsing
    info = client._parse_info(data)
    assert info["account_number"] == "1234567890"
    assert info["bank_code"] == "2010"
    assert isinstance(info["balance"], float)
    assert info["account_number_full"] == "1234567890/2010"
    
    # Test transaction parsing
    transactions = list(client._parse_transactions(data))
    assert len(transactions) == 2
    
    first_trans = transactions[0]
    assert first_trans["date"] == date(2016, 8, 3)
    assert isinstance(first_trans["amount"], float)
    assert first_trans["amount"] == -130.0
    assert first_trans["currency"] == "CZK"
    assert first_trans["account_number_full"] is None  # No account info in transaction


def test_fiobank_integration_decimal():
    """Test that FioBank integration works with Decimal mode."""
    client = FioBank("test_token", decimal=True)
    
    # Load test data
    test_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else 'tests'
    with open(os.path.join(test_dir, "transactions.json")) as f:
        data = json.load(f)
    
    # Test info parsing
    info = client._parse_info(data)
    assert isinstance(info["balance"], Decimal)
    
    # Test transaction parsing
    transactions = list(client._parse_transactions(data))
    first_trans = transactions[0]
    assert isinstance(first_trans["amount"], Decimal)


def test_schemas_removed():
    """Test that old schema attributes are removed."""
    client = FioBank("test_token")
    
    # These should no longer exist
    assert not hasattr(client, "transaction_schema")
    assert not hasattr(client, "info_schema")