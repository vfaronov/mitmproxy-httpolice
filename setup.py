import io
import os
import re

from setuptools import setup


with io.open(os.path.join('mitmproxy_httpolice.py')) as f:
    code = f.read()
    version = re.search(u"__version__ = '(.*)'", code).group(1)

with io.open('README.rst') as f:
    long_description = f.read()


setup(
    name='mitmproxy-HTTPolice',
    version=version,
    description='mitmproxy integration for HTTPolice',
    long_description=long_description,
    url='https://github.com/vfaronov/mitmproxy-httpolice',
    author='Vasiliy Faronov',
    author_email='vfaronov@gmail.com',
    license='MIT',
    python_requires='>= 3.6',
    install_requires=[
        'mitmproxy >= 4.0.4',
        'HTTPolice >= 0.5.0',
    ],
    py_modules=['mitmproxy_httpolice'],
    zip_safe=False,         # mitmproxy needs to read our module as a file
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Quality Assurance',
    ],
    keywords='HTTP message request response standards RFC validator proxy',
)
