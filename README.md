# fiobank

Little library implementing [Fio Bank API](http://www.fio.cz/bank-services/internetbanking-api) in Python.

## Status: ACTIVE

Under active development and maintenance. [Pull requests](http://help.github.com/send-pull-requests/) welcome! :-)

## Installation

```bash
$ pip install fiobank
```

## Usage

Initialization of client:

```python
>>> from fiobank import FioBank
>>> client = FioBank(token='...')
```

Account information:

```python
>>> client.info()
{'currency': 'CZK', 'account_number_full': 'XXXXXXXXXX/2010', 'balance': 42.00, 'account_number': 'XXXXXXXXXX', 'bank_code': '2010'}
```

Listing transactions within time period:

```python
>>> gen = client.period('2013-01-20', '2013-03-20')
>>> list(gen)[0]
{'comment': u'N\xe1kup: IKEA CR, BRNO, CZ, dne 17.1.2013, \u010d\xe1stka  2769.00 CZK', 'recipient_message': u'N\xe1kup: IKEA CR, BRNO, CZ, dne 17.1.2013, \u010d\xe1stka  2769.00 CZK', 'user_identifiaction': u'N\xe1kup: IKEA CR, BRNO, CZ, dne 17.1.2013, \u010d\xe1stka  2769.00 CZK', 'currency': 'CZK', 'amount': -2769.0, 'instruction_id': 'XXXXXXXXXX', 'executor': u'Vilém Fusek', 'date': datetime.date(2013, 1, 20), 'type': u'Platba kartou', 'transaction_id': 'XXXXXXXXXX'}
```

Listing transactions from single account statement:

```python
>>> client.statement(2013, 1)  # 1 is January only by coincidence - arguments mean 'first statement of 2013'
```

Listing latest transactions:

```python
>>> client.last()  # return transactions added from last listing
>>> client.last(from_id='...')  # sets cursor to given transaction_id and returns following transactions
>>> client.last(from_date='2013-03-01')  # sets cursor to given date and returns following transactions
```

For further information [read code](https://github.com/honzajavorek/fiobank/blob/master/fiobank.py).


## License: ISC

© 2013 Jan Javorek <jan.javorek@gmail.com>

This work is licensed under [ISC license](https://en.wikipedia.org/wiki/ISC_license).
