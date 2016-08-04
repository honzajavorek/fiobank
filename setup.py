# -*- coding: utf-8 -*-


from __future__ import print_function

import sys
from setuptools import setup

try:
    from semantic_release import setup_hook
    setup_hook(sys.argv)
except ImportError:
    message = "Unable to locate 'semantic_release', releasing won't work"
    print(message, file=sys.stderr)

try:
    import pypandoc
    long_description = pypandoc.convert_file('README.md', 'rst')
except ImportError:
    message = (
        "Unable to locate 'pypandoc', long description of the 'fiobank'"
        "package won't be available"
    )
    print(message, file=sys.stderr)
    long_description = ''


version = '1.1.0'


install_requires = ['requests', 'six']
tests_require = ['pytest-runner', 'pytest', 'flake8', 'responses', 'mock']
release_requires = ['pypandoc', 'python-semantic-release']


setup(
    name='fiobank',
    version=version,
    description='Fio Bank API in Python',
    long_description=long_description,
    author='Honza Javorek',
    author_email='mail@honzajavorek.cz',
    url='https://github.com/honzajavorek/fiobank',
    license=open('LICENSE').read(),
    py_modules=('fiobank',),
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={
        'tests': tests_require,
        'release': release_requires,
    },
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet',
    ),
    keywords='bank api wrapper sdk fio'
)
