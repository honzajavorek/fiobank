# -*- coding: utf-8 -*-


from __future__ import unicode_literals

from datetime import date, datetime

import pytest
from fiobank import coerce_date


@pytest.mark.parametrize('test_input', [
    date(2015, 8, 3),
    datetime(2015, 8, 3, 21, 3, 42),
    '2015-08-03T21:03:42',
])
def test_coerce_date(test_input):
    assert coerce_date(test_input) == date(2015, 8, 3)


@pytest.mark.parametrize('test_input', [42, True])
def test_coerce_date_invalid_type(test_input):
    with pytest.raises(TypeError):
        coerce_date(test_input)


@pytest.mark.parametrize('test_input', ['21:03:42', 'fio@fio.cz'])
def test_coerce_date_invalid_value(test_input):
    with pytest.raises(ValueError):
        coerce_date(test_input)
