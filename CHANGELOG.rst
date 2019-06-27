History of changes
==================


0.9.0 - 2019-06-27
~~~~~~~~~~~~~~~~~~
- You can now view full reports `directly from mitmproxy`_,
  without saving them to a file first.

.. _directly from mitmproxy:
   https://mitmproxy-httpolice.readthedocs.io/page/walkthrough.html#inmemory


0.8.0 - 2019-03-03
~~~~~~~~~~~~~~~~~~
This version is for mitmproxy 4.


0.7.1 - 2018-05-20
~~~~~~~~~~~~~~~~~~
This version adds an explicit requirement for mitmproxy version less than 4.
A new version compatible with mitmproxy 4 and/or higher will be released
eventually, when time permits.


0.7.0 - 2018-03-31
~~~~~~~~~~~~~~~~~~
- Overhaul for mitmproxy 3.

- Now focuses on closer integration with mitmproxy’s interactive features:

  - `commands`_ to produce reports on any flows
  - `options`_ that can be changed on the fly
  - marks on flows with problems
  - better display of notices in flow details

- At least for now, the original approach of writing a report
  non-interactively (options ``-w``, ``--tail``) is not supported.
  You need the ``mitmproxy`` tool, not ``mitmdump`` or ``mitmweb``.

- See `docs`_ for details.

.. _commands: https://docs.mitmproxy.org/stable/concepts-commands/
.. _options: https://docs.mitmproxy.org/stable/concepts-options/


0.6.1 - 2017-08-02
~~~~~~~~~~~~~~~~~~
- Fixed dumping reports to non-seekable files (like ``-w /dev/stdout``).
- Fixed ``--tail`` with small (text) reports.


0.6.0 - 2017-03-12
~~~~~~~~~~~~~~~~~~

Added
-----
- A new ``--tail`` option to regenerate the report on every new exchange,
  so you can inspect traffic as it comes (see `docs`_).

- HTTPolice now writes brief summaries to mitmproxy’s event log, like this::

    HTTPolice found 1 errors, 2 comments in: GET /api/v1/ - 200 OK

  (The event log is printed to the console when you use ``mitmdump``,
  or to the “Event log” pane when you press the ‘e’ key in ``mitmproxy``.)

- In the ``mitmproxy`` console UI, you can now see a brief report
  for every individual exchange on its “Detail” pane (see `docs`_).

.. _docs: https://mitmproxy-httpolice.readthedocs.io/

Changed
-------
- The output file is now specified with the ``-w`` option instead of
  just a positional argument, for example::

    $ mitmdump -s "`python3 -m mitmproxy_httpolice` -w report.txt"

  This ``-w`` option is actually *optional*: you can omit it
  if you only want to view the reports in the console UI, for example.


0.5.1 - 2017-02-28
~~~~~~~~~~~~~~~~~~
Fixed an error that happened on many/most HTTP/2 requests
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
