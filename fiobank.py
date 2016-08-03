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
        'ID pohybu': ('transaction_id', str),
        'Datum': ('date', str),
        'Objem': ('amount', float),
        'Měna': ('currency', str),
        'Protiúčet': ('account_number', str),
        'Název protiúčtu': ('account_name', str),
        'Kód banky': ('bank_code', str),
        'BIC': ('bic', str),
        'Název banky': ('bank_name', str),
        'KS': ('constant_symbol', str),
        'VS': ('variable_symbol', str),
        'SS': ('specific_symbol', str),
        'Uživatelská identifikace': ('user_identification', str),
        'Zpráva pro příjemce': ('recipient_message', str),
        'Typ': ('type', str),
        'Provedl': ('executor', str),
        'Upřesnění': ('specification', str),
        'Komentář': ('comment', str),
        'ID pokynu': ('instruction_id', str),
    }

    info_schema = {
        'accountId': ('account_number', str),
        'bankId': ('bank_code', str),
        'currency': ('currency', str),
        'IBAN': ('iban', str),
        'BIC': ('bic', str),
        'closingBalance': ('balance', float),
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
                field_name, type_ = schema[column_data['name']]
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
