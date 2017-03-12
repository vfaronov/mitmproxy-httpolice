# -*- coding: utf-8; -*-
# pylint: disable=redefined-outer-name

"""Spin up an actual mitmdump process and run a few requests through it."""

import io
import os
import random
import socket
import ssl
import subprocess
import tempfile
import time

import hyper
import hyper.tls
import pytest


class RealMitmdump:

    # pylint: disable=attribute-defined-outside-init

    host = 'localhost'

    def __init__(self):
        self.port = random.randint(1024, 65535)
        self.extra_options = []

    def start(self):
        config_path = os.path.join(
            os.path.dirname(__file__), 'tools', 'mitmproxy-config')
        fd, self.report_path = tempfile.mkstemp()
        os.close(fd)
        script_path = subprocess.check_output(
            ['python3', '-m', 'mitmproxy_httpolice']).decode().strip()
        args = (['--conf', config_path, '-p', str(self.port)] +
                self.extra_options +
                ['-s', "'%s' -w '%s'" % (script_path, self.report_path)])
        self.process = subprocess.Popen(['mitmdump'] + args)
        time.sleep(5)       # Give it some time to get up and running

    # This whole thing is actually easier to do by hand
    # than with either `httplib` or `urllib2`,
    # and I don't want to pull in Requests just for this.

    def send_request(self, data):
        # pylint: disable=no-member
        sock = socket.create_connection(('localhost', self.port))
        sock.sendall(data)
        sock.recv(4096)
        sock.close()

    def send_tunneled_request(self, host, port, data):
        # We need our own TLS context that does not verify certificates.
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        sock = socket.create_connection((self.host, self.port))
        connect = ('CONNECT {0}:{1} HTTP/1.1\r\n'
                   'Host: {0}\r\n'
                   '\r\n'.format(host, port))
        sock.sendall(connect.encode('iso-8859-1'))
        assert sock.recv(4096).startswith(b'HTTP/1.1 2')
        sock = context.wrap_socket(sock, server_hostname=host)
        sock.sendall(data)
        sock.recv(4096)
        sock.close()

    def done(self, collect=True):
        self.process.terminate()
        self.process.communicate()
        if collect:
            with io.open(self.report_path, 'rb') as f:
                self.report = f.read()
        if os.path.exists(self.report_path):
            os.remove(self.report_path)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, _exc_value, _traceback):
        self.done(collect=exc_type is None)


@pytest.fixture
def real_mitmdump(request):                  # pylint: disable=unused-argument
    return RealMitmdump()


def test_http11_proxy(real_mitmdump):
    with real_mitmdump:
        real_mitmdump.send_request(
            b'GET http://httpbin.org/response-headers?ETag=foobar HTTP/1.1\r\n'
            b'Host: httpbin.org\r\n'
            b'\r\n'
        )
    assert real_mitmdump.report == (
        b'------------ request: GET /response-headers?ETag=foobar\n'
        b'C 1070 Missing User-Agent header\n'
        b'------------ response: 200 OK\n'
        b'E 1000 Syntax error in ETag header\n'
    )


def test_http11_tunnel(real_mitmdump):
    with real_mitmdump:
        real_mitmdump.send_tunneled_request(
            'httpd.apache.org', 443,
            b'OPTIONS * HTTP/1.1\r\n'
            b'Host: ietf.org\r\n'
            b'User-Agent: demo\r\n'
            b'Content-Length: 14\r\n'
            b'\r\n'
            b'Hello world!\r\n'
        )
    assert real_mitmdump.report == (
        b'------------ request: OPTIONS *\n'
        b'C 1041 Body should have a Content-Type\n'
        b'E 1062 OPTIONS request with a body needs Content-Type\n'
    )


@pytest.mark.skipif(ssl.OPENSSL_VERSION_INFO < (1, 0, 2),
                    reason='HTTP/2 needs ALPN, which needs OpenSSL 1.0.2+')
def test_http2_reverse(real_mitmdump):      # pragma: no cover
    # A TLS context that does not verify certificates.
    context = hyper.tls.init_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    real_mitmdump.extra_options = ['--reverse', 'https://nghttp2.org']
    with real_mitmdump:
        conn = hyper.HTTPConnection(real_mitmdump.host, real_mitmdump.port,
                                    secure=True, ssl_context=context,
                                    enable_push=True)
        conn.request('GET', '/')
        conn.get_response()
        # Wait for the ``PUSH_PROMISE``.
        time.sleep(3)

    # nghttp2.org currently has some problems that we can't rely on
    # (notices 1277 and 1109), so we check only specific things.
    assert (b'------------ request: GET https://nghttp2.org/\n'
            b'C 1070 Missing User-Agent header\n') in real_mitmdump.report
