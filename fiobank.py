# -*- coding: utf-8 -*-


from __future__ import unicode_literals

import re
from datetime import datetime, date

import six
import requests


__all__ = ('FioBank',)


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


class FioBank(object):

    base_url = 'https://www.fio.cz/ib_api/rest/'

    actions = {
        'periods': 'periods/{token}/{from_date}/{to_date}/transactions.json',
        'by-id': 'by-id/{token}/{year}/{number}/transactions.json',
        'last': 'last/{token}/transactions.json',
        'set-last-id': 'set-last-id/{token}/{from_id}/',
        'set-last-date': 'set-last-date/{token}/{from_date}/',
    }

    transaction_schema = {
        'id pohybu': ('transaction_id', str),
        'datum': ('date', str),
        'objem': ('amount', float),
        'měna': ('currency', str),
        'protiúčet': ('account_number', str),
        'název protiúčtu': ('account_name', str),
        'kód banky': ('bank_code', str),
        'bic': ('bic', str),
        'název banky': ('bank_name', str),
        'ks': ('constant_symbol', str),
        'vs': ('variable_symbol', str),
        'ss': ('specific_symbol', str),
        'uživatelská identifikace': ('user_identification', str),
        'zpráva pro příjemce': ('recipient_message', str),
        'typ': ('type', str),
        'provedl': ('executor', str),
        'upřesnění': ('specification', str),
        'komentář': ('comment', str),
        'id pokynu': ('instruction_id', str),
    }

    info_schema = {
        'accountid': ('account_number', str),
        'bankid': ('bank_code', str),
        'currency': ('currency', str),
        'iban': ('iban', str),
        'bic': ('bic', str),
        'closingbalance': ('balance', float),
    }

    _amount_re = re.compile(r'\-?[\d+](\.\d+)? [A-Z]{3}')

    def __init__(self, token):
        self.token = token

    def _request(self, action, **params):
        template = self.base_url + self.actions[action]
        url = template.format(token=self.token, **params)

        response = requests.get(url)
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
                field_name, type_ = self.info_schema[key]
                value = sanitize_value(value, type_)
                info[field_name] = value

        # make some refinements
        info['account_number_full'] = (info['account_number'] +
                                       '/' + info['bank_code'])

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
                field_name, type_ = schema[column_data['name'].lower()]
                value = sanitize_value(column_data['value'], type_)
                trans[field_name] = value

            # make some refinements
            is_amount = self._amount_re.match
            if 'specification' in trans and is_amount(trans['specification']):
                amount, currency = trans['specification'].split(' ')
                trans['original_amount'] = float(amount)
                trans['original_currency'] = currency

            if 'date' in trans:
                trans['date'] = coerce_date(trans['date'])

            if 'account_number' in trans and 'bank_code' in trans:
                trans['account_number_full'] = (trans['account_number'] +
                                                '/' + trans['bank_code'])

            # generate transaction data
            yield trans

    def info(self):
        today = date.today()
        data = self._request('periods', from_date=today, to_date=today)
        # with open('info.json', 'w') as f:
        #     import json
        #     json.dump(data, f, indent=4)
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
        assert not (from_id and from_date), 'Only one constraint is allowed.'

        if from_id:
            self._request('set-last-id', from_id=from_id)
        elif from_date:
            self._request('set-last-date', from_date=coerce_date(from_date))

        return self._parse_transactions(self._request('last'))
