import pytest
from fiobank import sanitize_value


@pytest.mark.parametrize('test_input,expected', [
    ('', ''),
    ('fio', 'fio'),
    (0, 0),
    (False, False),
    (None, None),
    (123, 123),
    (30.8, 30.8),
])
def test_sanitize_value_no_effect(test_input, expected):
    sanitize_value(test_input) == expected


@pytest.mark.parametrize('test_input,expected', [
    ('     \n     ', ''),
    ('\nfio    ', 'fio'),
])
def test_sanitize_value_strip(test_input, expected):
    sanitize_value(test_input) == expected


@pytest.mark.parametrize('test_input,convert,expected', [
    ('abc', str, 'abc'),
    ('žluťoučký kůň', str, 'žluťoučký kůň'),
    (None, str, None),
    (None, bool, None),
    (123, str, '123'),
    (30.8, str, '30.8'),
    (0, int, 0),
    (30.8, int, 30),
    (False, bool, False),
])
def test_sanitize_value_convert(test_input, convert, expected):
    sanitize_value(test_input, convert) == expected
