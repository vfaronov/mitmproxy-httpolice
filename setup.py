# -*- coding: utf-8; -*-

import io
import os
import re

from setuptools import setup


with io.open(os.path.join('mitmproxy_httpolice.py')) as f:
    code = f.read()
    version = re.search(u"__version__ = '(.*)'", code).group(1)

with io.open('README.rst') as f:
    long_description = f.read()

with io.open('requirements.in') as f:
    install_requires = [line for line in f
                        if line and not line.startswith('#')]


setup(
    name='mitmproxy-HTTPolice',
    version=version,
    description='mitmproxy integration for HTTPolice',
    long_description=long_description,
    url='https://github.com/vfaronov/mitmproxy-httpolice',
    author='Vasiliy Faronov',
    author_email='vfaronov@gmail.com',
    license='MIT',
    install_requires=install_requires,
    py_modules=['mitmproxy_httpolice'],
    zip_safe=False,         # mitmproxy needs to read our module as a file
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Quality Assurance',
    ],
    keywords='HTTP message request response standards RFC lint check proxy',
)
