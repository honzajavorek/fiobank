from datetime import date, datetime

import pytest

from fiobank import coerce_date


@pytest.mark.parametrize(
    "test_input",
    [
        date(2016, 8, 3),
        datetime(2016, 8, 3, 21, 3, 42),
        "2016-08-03T21:03:42",
    ],
)
def test_coerce_date(test_input: "date | datetime | str"):
    assert coerce_date(test_input) == date(2016, 8, 3)


@pytest.mark.parametrize("test_input", [42, True])
def test_coerce_date_invalid_type(test_input: "int | bool"):
    with pytest.raises(TypeError):
        coerce_date(test_input)  # type: ignore


@pytest.mark.parametrize("test_input", ["21:03:42", "fio@fio.cz"])
def test_coerce_date_invalid_value(test_input: str):
    with pytest.raises(ValueError):
        coerce_date(test_input)
