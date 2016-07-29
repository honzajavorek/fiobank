# -*- coding: utf-8 -*-


import sys
from setuptools import setup

try:
    from semantic_release import setup_hook
    setup_hook(sys.argv)
except ImportError:
    pass


version = '0.0.5'


setup(
    name='fiobank',
    version=version,
    description='Little library implementing Fio Bank API in Python',
    long_description=open('README.md').read(),
    author='Honza Javorek',
    author_email='mail@honzajavorek.cz',
    url='https://github.com/honzajavorek/fiobank',
    license=open('LICENSE').read(),
    py_modules=('fiobank',),
    install_requires=['requests>=1.0.0'],
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet',
    )
)
