# -*- coding: utf-8 -*-

import re
from datetime import datetime, date

import requests


__all__ = ('FioBank',)


def coerce_date(value):
    if isinstance(value, date):
        return value
    elif isinstance(value, datetime):
        return value.date()
    else:
        return datetime.strptime(value[:10], '%Y-%m-%d').date()


def sort_person_names(value):
    if ',' in value:
        parts = value.split(',')
        parts.reverse()
        return ' '.join(parts).strip()
    return value


def sanitize_value(value, convert=None):
    if isinstance(value, basestring):
        value = value.strip() or None
    if convert and value:
        return convert(value)
    return value


def is_amount(value):
    return bool(re.match(r'\-?[\d+](\.\d+)? [A-Z]{3}', value))


class Transaction(dict):

    def __init__(self, *args, **kwargs):
        super(Transaction, self).__init__(*args, **kwargs)

        if 'specification' in self and is_amount(self['specification']):
            amount, currency = self['specification'].split(' ')
            self['original_amount'] = float(amount)
            self['original_currency'] = currency

        if 'date' in self:
            self['date'] = coerce_date(self['date'])

        if 'executor' in self:
            self['executor'] = sort_person_names(self['executor'])

        if 'account_number' in self and 'bank_code' in self:
            self['account_number_full'] = (self['account_number'] +
                                           '/' + self['bank_code'])


class Info(dict):

    def __init__(self, *args, **kwargs):
        super(Info, self).__init__(*args, **kwargs)

        self['account_number_full'] = (self['account_number'] +
                                       '/' + self['bank_code'])


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
        u'ID pohybu': ('transaction_id', str),
        u'Datum': ('date', unicode),
        u'Objem': ('amount', float),
        u'Měna': ('currency', str),
        u'Protiúčet': ('account_number', str),
        u'Název protiúčtu': ('account_name', unicode),
        u'Kód banky': ('bank_code', str),
        u'BIC': ('bic', str),
        u'Název banky': ('bank_name', unicode),
        u'KS': ('constant_symbol', str),
        u'VS': ('variable_symbol', str),
        u'SS': ('specific_symbol', str),
        u'Uživatelská identifikace': ('user_identifiaction', unicode),
        u'Zpráva pro příjemce': ('recipient_message', unicode),
        u'Typ': ('type', unicode),
        u'Provedl': ('executor', unicode),
        u'Upřesnění': ('specification', unicode),
        u'Komentář': ('comment', unicode),
        u'ID pokynu': ('instruction_id', str),
    }

    info_schema = {
        u'accountId': ('account_number', str),
        u'bankId': ('bank_code', str),
        u'currency': ('currency', str),
        u'IBAN': ('iban', str),
        u'BIC': ('bic', str),
        u'closingBalance': ('balance', float),
    }

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
        input_data = {}
        for key, value in data['accountStatement']['info'].items():
            if key in self.info_schema:
                field_name, type_ = self.info_schema[key]
                value = sanitize_value(value, type_)
                input_data[field_name] = value
        return Info(input_data)

    def _parse_transactions(self, data):
        schema = self.transaction_schema
        entries = data['accountStatement']['transactionList']['transaction']

        for entry in entries:
            input_data = {}
            for column_name, column_data in entry.items():
                if not column_data:
                    continue
                field_name, type_ = schema[column_data['name']]
                value = sanitize_value(column_data['value'], type_)
                input_data[field_name] = value
            yield Transaction(input_data)

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
        assert not (from_id and from_date), "Only one constraint is allowed."

        if from_id:
            self._request('set-last-id', from_id=from_id)
        elif from_date:
            self._request('set-last-date', from_date=coerce_date(from_date))

        return self._parse_transactions(self._request('last'))
