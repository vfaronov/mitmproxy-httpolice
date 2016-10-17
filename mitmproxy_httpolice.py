# -*- coding: utf-8; -*-

import argparse
import io
import os

import httpolice


__version__ = '0.4.0'

reports = {'text': httpolice.text_report, 'html': httpolice.html_report}


def start(argv=None):
    parser = argparse.ArgumentParser(prog=os.path.basename(__file__),
                                     add_help=False)
    parser.add_argument('-o', '--output', choices=reports, default='text')
    parser.add_argument('-s', '--silence', metavar='ID',
                        type=int, action='append')
    parser.add_argument('report_path')
    args = parser.parse_args(argv)
    return MitmproxyHTTPolice(args.report_path, args.output, args.silence)


class MitmproxyHTTPolice(object):

    def __init__(self, report_path, output_format, silence=None):
        self.report_path = os.path.expanduser(report_path)
        self.output_format = output_format
        self.silence = silence or []
        self.exchanges = []

        # Open the output file right now, because if it's wrong,
        # we don't want to wait until the end and lose all collected data.
        self.report_file = io.open(self.report_path, 'wb')

    def response(self, flow):
        req = construct_request(flow)
        resp = construct_response(flow)
        exch = httpolice.Exchange(req, [resp])
        exch.silence(self.silence)
        httpolice.check_exchange(exch)
        self.exchanges.append(exch)

    def done(self):
        with self.report_file:
            report = reports[self.output_format]
            report(self.exchanges, self.report_file)


def construct_request(flow):
    version, headers, body = extract_message_basics(flow.request)
    scheme = decode(flow.request.scheme)
    method = decode(flow.request.method)

    # Authority-form and absolute-form requests in the tunnel
    # are simply rejected as errors by mitmproxy, closing the connection.
    target = decode(flow.request.path)

    if version == u'HTTP/2':
        pseudo_headers = httpolice.helpers.pop_pseudo_headers(headers)
        authority = pseudo_headers.get(u':authority')
        has_host = any(k.lower() == u'host' for (k, v) in headers)
        if authority and not has_host and target.startswith(u'/'):
            # Reconstruct HTTP/2's equivalent of
            # the "absolute form" of request target (RFC 7540 Section 8.1.2.3).
            target = scheme + u'://' + authority + target

    return httpolice.Request(scheme, method, target, version, headers, body)


def construct_response(flow):
    version, headers, body = extract_message_basics(flow.response)
    status = flow.response.status_code
    reason = decode(flow.response.reason)
    if version == u'HTTP/2':
        httpolice.helpers.pop_pseudo_headers(headers)
    return httpolice.Response(version, status, reason, headers, body)


def extract_message_basics(msg):
    version = decode(msg.http_version)
    if version == u'HTTP/2.0':
        version = u'HTTP/2'
    headers = [(decode(k), v) for (k, v) in msg.headers.fields]
    body = msg.raw_content
    return version, headers, body


def decode(s):
    if isinstance(s, bytes):
        return s.decode('iso-8859-1')
    else:
        return s


if __name__ == '__main__':
    # Print the path to this script,
    # for substitution into the mitmproxy command.
    print(__file__)
