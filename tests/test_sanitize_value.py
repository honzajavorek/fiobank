# -*- coding: utf-8 -*-


from __future__ import unicode_literals

import six
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
    ('abc', six.text_type, 'abc'),
    ('žluťoučký kůň', six.text_type, 'žluťoučký kůň'),
    (None, six.text_type, None),
    (None, bool, None),
    (123, six.text_type, '123'),
    (30.8, six.text_type, '30.8'),
    (0, int, 0),
    (30.8, int, 30),
    (False, bool, False),
])
def test_sanitize_value_convert(test_input, convert, expected):
    sanitize_value(test_input, convert) == expected
