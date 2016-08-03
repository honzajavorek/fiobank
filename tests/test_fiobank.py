# -*- coding: utf-8 -*-


from __future__ import unicode_literals

import re
import os
import uuid
from collections import namedtuple

import json
import pytest
import responses
from fiobank import FioBank


Fixture = namedtuple('Fixture', ['api_response', 'return_value'])


def create_url(path, **kwargs):
    return re.compile((FioBank.base_url + path).format(**kwargs))


def load_body(name):
    fixtures_dir = os.path.dirname(__file__) + '/fixtures'
    with open((fixtures_dir + '/{}.json').format(name)) as f:
        return json.load(f)


@pytest.fixture(scope='function')
def token():
    return uuid.uuid4()


@pytest.yield_fixture(scope='function')
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture(scope='function')
def info(mocked_responses, token):
    url = create_url(r'periods/{token}/[^/]+/[^/]+/transactions\.json',
                     token=token)
    body = load_body('periods')
    mocked_responses.add(responses.GET, url, json=body)

    client = FioBank(token)
    return Fixture(body, client.info())


def test_info(info):
    assert frozenset(info.return_value.keys()) == frozenset([
        'account_number_full', 'account_number', 'bank_code',
        'currency', 'iban', 'bic', 'balance',
    ])


def test_info_account_number(info):
    assert (
        info.return_value['account_number'] ==
        info.api_response['accountStatement']['info']['accountId']
    )


def test_info_account_number_full(info):
    assert (
        info.return_value['account_number_full'] ==
        '{}/{}'.format(
            info.api_response['accountStatement']['info']['accountId'],
            info.api_response['accountStatement']['info']['bankId']
        )
    )


def test_info_bank_code(info):
    assert (
        info.return_value['bank_code'] ==
        info.api_response['accountStatement']['info']['bankId']
    )


def test_info_currency(info):
    assert (
        info.return_value['currency'] ==
        info.api_response['accountStatement']['info']['currency']
    )


def test_info_iban(info):
    assert (
        info.return_value['iban'] ==
        info.api_response['accountStatement']['info']['iban']
    )


def test_info_bic(info):
    assert (
        info.return_value['bic'] ==
        info.api_response['accountStatement']['info']['bic']
    )


def test_info_balance(info):
    assert (
        info.return_value['balance'] ==
        info.api_response['accountStatement']['info']['closingBalance']
    )


def test_info_is_case_insensitive():
    client = FioBank('...')
    info = client._parse_info({
        'accountStatement': {
            'info': {
                'acCOUNTid': '30',
                'BANKid': '8',
            }
        }
    })
    assert info['account_number'] == '30'
