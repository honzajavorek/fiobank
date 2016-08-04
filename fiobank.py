# -*- coding: utf-8 -*-


from __future__ import unicode_literals

import re
from datetime import datetime, date

import six
import requests


__all__ = ('FioBank', 'ThrottlingError')


str = six.text_type


def coerce_date(value):
    if isinstance(value, datetime):
        return value.date()
    elif isinstance(value, date):
        return value
    else:
        return datetime.strptime(value[:10], '%Y-%m-%d').date()


def sanitize_value(value, convert=None):
    if isinstance(value, six.string_types):
        value = value.strip() or None
    if convert and value is not None:
        return convert(value)
    return value


class ThrottlingError(Exception):
    """Throttling error raised when api is being used too fast."""

    def __str__(self):
        return 'Token should be used only once per 30s.'


class FioBank(object):

    base_url = 'https://www.fio.cz/ib_api/rest/'

    actions = {
        'periods': 'periods/{token}/{from_date}/{to_date}/transactions.json',
        'by-id': 'by-id/{token}/{year}/{number}/transactions.json',
        'last': 'last/{token}/transactions.json',
        'set-last-id': 'set-last-id/{token}/{from_id}/',
        'set-last-date': 'set-last-date/{token}/{from_date}/',
    }

    # http://www.fio.cz/xsd/IBSchema.xsd
    transaction_schema = {
        'column0': ('date', coerce_date),
        'column1': ('amount', float),
        'column2': ('account_number', str),
        'column3': ('bank_code', str),
        'column4': ('constant_symbol', str),
        'column5': ('variable_symbol', str),
        'column6': ('specific_symbol', str),
        'column7': ('user_identification', str),
        'column8': ('type', str),
        'column9': ('executor', str),
        'column10': ('account_name', str),
        'column12': ('bank_name', str),
        'column14': ('currency', str),
        'column16': ('recipient_message', str),
        'column17': ('instruction_id', str),
        'column18': ('specification', str),
        'column22': ('transaction_id', str),
        'column25': ('comment', str),
        'column26': ('bic', str),
    }

    info_schema = {
        'accountid': ('account_number', str),
        'bankid': ('bank_code', str),
        'currency': ('currency', str),
        'iban': ('iban', str),
        'bic': ('bic', str),
        'closingbalance': ('balance', float),
    }

    _amount_re = re.compile(r'\-?\d+(\.\d+)? [A-Z]{3}')

    def __init__(self, token):
        self.token = token

    def _request(self, action, **params):
        template = self.base_url + self.actions[action]
        url = template.format(token=self.token, **params)

        response = requests.get(url)
        if response.status_code == requests.codes['conflict']:
            raise ThrottlingError()

        response.raise_for_status()

        if response.content:
            return response.json()
        return None

    def _parse_info(self, data):
        # parse data from API
        info = {}
        for key, value in data['accountStatement']['info'].items():
            key = key.lower()
            if key in self.info_schema:
                field_name, convert = self.info_schema[key]
                value = sanitize_value(value, convert)
                info[field_name] = value

        # make some refinements
        self._add_account_number_full(info)

        # return data
        return info

    def _parse_transactions(self, data):
        schema = self.transaction_schema
        try:
            entries = data['accountStatement']['transactionList']['transaction']  # NOQA
        except TypeError:
            entries = []

        for entry in entries:
            # parse entry from API
            trans = {}
            for column_name, column_data in entry.items():
                if not column_data:
                    continue
                field_name, convert = schema[column_name.lower()]
                value = sanitize_value(column_data['value'], convert)
                trans[field_name] = value

            # add missing fileds with None values
            for column_data_name, (field_name, convert) in schema.items():
                trans.setdefault(field_name, None)

            # make some refinements
            specification = trans.get('specification')
            is_amount = self._amount_re.match
            if specification is not None and is_amount(specification):
                amount, currency = trans['specification'].split(' ')
                trans['original_amount'] = float(amount)
                trans['original_currency'] = currency
            else:
                trans['original_amount'] = None
                trans['original_currency'] = None

            self._add_account_number_full(trans)

            # generate transaction data
            yield trans

    def _add_account_number_full(self, obj):
        account_number = obj.get('account_number')
        bank_code = obj.get('bank_code')

        if account_number is not None and bank_code is not None:
            account_number_full = '{}/{}'.format(account_number, bank_code)
        else:
            account_number_full = None

        obj['account_number_full'] = account_number_full

    def info(self):
        today = date.today()
        data = self._request('periods', from_date=today, to_date=today)
        return self._parse_info(data)

    def period(self, from_date, to_date):
        data = self._request('periods',
                             from_date=coerce_date(from_date),
                             to_date=coerce_date(to_date))
        return self._parse_transactions(data)

    def statement(self, year, number):
        data = self._request('by-id', year=year, number=number)
        return self._parse_transactions(data)

    def last(self, from_id=None, from_date=None):
        if from_id and from_date:
            raise ValueError('Only one constraint is allowed.')

        if from_id:
            self._request('set-last-id', from_id=from_id)
        elif from_date:
            self._request('set-last-date', from_date=coerce_date(from_date))

        return self._parse_transactions(self._request('last'))
