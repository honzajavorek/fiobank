import sys
from setuptools import setup

try:
    from semantic_release import setup_hook
    setup_hook(sys.argv)
except ImportError:
    message = "Unable to locate 'semantic_release', releasing won't work"
    print(message, file=sys.stderr)


version = '3.0.0'


install_requires = [
    'requests',
]
tests_require = [
    'pytest-runner',
    'pytest',
    'pylama',
    'responses',
    'mock',
    'coveralls',
    'pytest-cov',
]
release_requires = [
    'python-semantic-release',
]


setup(
    name='fiobank',
    version=version,
    description='Fio Bank API in Python',
    long_description=open('README.rst').read(),
    author='Honza Javorek',
    author_email='mail@honzajavorek.cz',
    url='https://github.com/honzajavorek/fiobank',
    license='ISC',
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
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet',
    ),
    keywords='bank api wrapper sdk fio'
)
