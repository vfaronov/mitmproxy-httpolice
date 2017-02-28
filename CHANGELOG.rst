Changelog
=========

All notable changes to mitmproxy-HTTPolice will be documented in this file.

This project adheres to `Semantic Versioning <http://semver.org/>`_
(which means it is unstable until 1.0).


Unreleased
~~~~~~~~~~
- Fixed an error that happened on many/most HTTP/2 requests
  (those without a Host header).


0.5.0 - 2017-01-14
~~~~~~~~~~~~~~~~~~
No interesting changes; just update docs and packaging
for better compatibility with Python 3.6 and mitmproxy 1.0.
This version also drops support for Python 2. If you need Python 2,
use ``mitmproxy==0.18.2`` and ``mitmproxy-HTTPolice==0.4.0``.


0.4.0 - 2016-10-17
~~~~~~~~~~~~~~~~~~
This release is compatible with mitmproxy 0.18+, and **only** 0.18+
(because mitmproxy 0.18 has a new, backward-incompatible API).
Note that mitmproxy (and thus mitmproxy-HTTPolice) now supports Python 3.5+.


0.3.0 - 2016-08-14
~~~~~~~~~~~~~~~~~~
Technical release. No interesting changes.


0.2.0 - 2016-05-08
~~~~~~~~~~~~~~~~~~
Initial release as a separate distribution.
