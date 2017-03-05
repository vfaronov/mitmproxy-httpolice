# -*- coding: utf-8; -*-
# pylint: disable=no-name-in-module,import-error

import io
import os
import tempfile

from mitmproxy.net.http import Headers
from mitmproxy.test import taddons, tflow, tutils
import pytest

import mitmproxy_httpolice


class Bench:

    def __init__(self):
        self.opts = []
        self.context = taddons.context()
        self.report_path = None
        self.script_obj = None
        self.report = None

    def start(self):
        fd, self.report_path = tempfile.mkstemp()
        os.close(fd)
        argv = self.opts + [self.report_path]
        self.script_obj = mitmproxy_httpolice.start(argv)

    def flow(self, req, resp):
        self.script_obj.response(tflow.tflow(req=req, resp=resp))

    def done(self):
        self.script_obj.done()
        with io.open(self.report_path, 'rb') as f:
            self.report = f.read()

    def __enter__(self):
        self.context.__enter__()
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.done()
        self.context.__exit__(exc_type, exc_value, traceback)
        if os.path.exists(self.report_path):
            os.unlink(self.report_path)


@pytest.fixture
def bench(request):                     # pylint: disable=unused-argument
    return Bench()


def test_simple(bench):                 # pylint: disable=redefined-outer-name
    with bench:
        bench.flow(
            tutils.treq(
                scheme='http', host='example.com', port=80,
                method='GET', path='/', http_version='HTTP/1.1',
                headers=Headers([(b'host', b'example.com'),
                                 (b'User-Agent', b'demo')]),
                content=b'',
            ),
            tutils.tresp(
                http_version='HTTP/1.1', status_code=200, reason='OK',
                headers=Headers([
                    (b'Content-Type', b'text/plain'),
                    (b'Content-Length', b'14'),
                    (b'Date', b'Tue, 03 May 2016 14:13:34 GMT'),
                ]),
                content=b'Hello world!\r\n',
            ),
        )
    assert bench.report == b''


def test_complex(bench):               # pylint: disable=redefined-outer-name
    with bench:
        bench.flow(
            tutils.treq(
                scheme='http', host='example.com', port=80,
                method='POST', path='/foo-bar?baz=qux',
                http_version='HTTP/1.1',
                headers=Headers([(b'host', b'example.com'),
                                 (b'User-Agent', b'demo'),
                                 (b'Transfer-Encoding', b'chunked'),
                                 (b'content-type', b'application/json')]),
                content=b'{foo: "bar"}',
            ),
            tutils.tresp(
                http_version='HTTP/1.1',
                status_code=201, reason=u'Très bien'.encode('iso-8859-1'),
                headers=Headers([(b'Content-Type', b'text/plain'),
                                 (b'Content-Length', b'14'),
                                 (b'Date', b'Tue, 03 May 2016 14:13:34 GMT')]),
                content=b'Hello world!\r\n',
            ),
        )
        bench.flow(
            tutils.treq(
                scheme='http', host='example.com', port=80,
                method='GET', path='/', http_version='HTTP/1.1',
                headers=Headers([(b'host', b'example.com'),
                                 (b'User-Agent', b'demo'),
                                 (b'If-None-Match', b'"quux"')]),
                content=b'',
            ),
            tutils.tresp(
                http_version='HTTP/1.1',
                status_code=304, reason='Not Modified',
                headers=Headers([(b'Content-Type', b'text/plain'),
                                 (b'Date', b'Tue, 03 May 2016 14:13:34 GMT')]),
                content=b'',
            ),
        )

    assert bench.report == (
        b'------------ request: POST /foo-bar?baz=qux\n'
        b'E 1038 Bad JSON body\n' +
        u'------------ response: 201 Très bien\n'.encode('utf-8') +
        b'C 1073 Possibly missing Location header\n'
        b'------------ request: GET /\n'
        b'------------ response: 304 Not Modified\n'
        b'C 1127 Content-Type in a 304 response\n'
    )


def test_http2(bench):          # pylint: disable=redefined-outer-name
    with bench:
        bench.flow(
            tutils.treq(
                scheme='https', host='example.com', port=443,
                method='GET', path='/index.html', http_version='HTTP/2.0',
                headers=Headers([(b':method', b'GET'),
                                 (b':scheme', b'https'),
                                 (b':authority', b'example.com'),
                                 (b':path', b'/index.html'),
                                 (b'user-agent', b'demo'),
                                 (b'if-match', b'quux')]),
                content=b'',
            ),
            tutils.tresp(
                http_version='HTTP/2.0', status_code=404, reason='',
                headers=Headers([(b':status', b'404'),
                                 (b'content-type', b'text/plain'),
                                 (b'content-length', b'14'),
                                 (b'date', b'Tue, 03 May 2016 14:13:34 GMT'),
                                 (b'connection', b'close')]),
                content=b'Hello world!\r\n',
            ),
        )
    assert bench.report == (
        b'------------ request: GET https://example.com/index.html\n'
        b'E 1000 Malformed if-match header\n'
        b'------------ response: 404 Not Found\n'
        b'E 1244 connection header in an HTTP/2 message\n'
    )


def test_html(bench):           # pylint: disable=redefined-outer-name
    bench.opts = ['-o', 'html']
    with bench:
        bench.flow(
            tutils.treq(
                scheme='http', host='example.com', port=80,
                method='GET', path=('/foo/bar' * 30), http_version='HTTP/1.1',
                headers=Headers([(b'host', b'example.com'),
                                 (b'User-Agent', b'Java')]),
                content=b'',
            ),
            tutils.tresp(
                http_version='HTTP/1.1', status_code=200, reason='OK',
                headers=Headers([
                    (b'Content-Type', b'text/plain'),
                    (b'Content-Length', b'14'),
                    (b'Date', b'Tue, 03 May 2016 14:13:34 GMT'),
                ]),
                content=b'Hello world!\r\n',
            ),
        )
    assert b'<h1>HTTPolice report</h1>' in bench.report


def test_silence(bench):         # pylint: disable=redefined-outer-name
    bench.opts = ['-s', '1087', '-s', '1194']
    with bench:
        bench.flow(
            tutils.treq(
                scheme='http', host='example.com', port=80,
                method='GET', path='/', http_version='HTTP/1.1',
                headers=Headers([(b'host', b'example.com'),
                                 (b'User-Agent', b'demo')]),
                content=b'',
            ),
            tutils.tresp(
                http_version='HTTP/1.1',
                status_code=401, reason='Unauthorized',
                headers=Headers([(b'Content-Type', b'text/plain'),
                                 (b'Content-Length', b'0')]),
                content=b'',
            ),
        )
    assert bench.report == (
        b'------------ request: GET /\n'
        b'------------ response: 401 Unauthorized\n'
        b'C 1110 401 response with no Date header\n'
    )
