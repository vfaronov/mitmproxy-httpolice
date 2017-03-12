# -*- coding: utf-8; -*-

import argparse
import collections
import io
import os

import httpolice
import mitmproxy.ctx


__version__ = '0.6.0'

reports = {'text': httpolice.text_report, 'html': httpolice.html_report}


def start(argv=None):
    parser = argparse.ArgumentParser(prog=os.path.basename(__file__),
                                     add_help=False)
    parser.add_argument('-w', '--write-report', metavar='PATH',
                        type=argparse.FileType('wb'))
    parser.add_argument('--tail', metavar='N', type=positive_int, default=None)
    parser.add_argument('-o', '--output', choices=reports, default='text')
    parser.add_argument('-s', '--silence', metavar='ID',
                        type=int, action='append', default=[])
    args = parser.parse_args(argv)
    if args.tail and not args.write_report:
        parser.error('--tail requires -w/--write-report')
    return MitmproxyHTTPolice(args.write_report, args.tail, args.output,
                              args.silence)


class MitmproxyHTTPolice:

    def __init__(self, report_file, tail, output_format, silence):
        self.report_file = report_file
        self.tail = tail
        self.output_format = output_format
        self.silence = silence
        if self.tail is None:
            self.exchanges = []
        else:
            self.exchanges = collections.deque(maxlen=self.tail)

    def response(self, flow):
        req = construct_request(flow)
        resp = construct_response(flow)
        exch = httpolice.Exchange(req, [resp])
        exch.silence(self.silence)
        httpolice.check_exchange(exch)
        self.exchanges.append(exch)
        if self.tail:
            self.dump_report()
        attach_report(exch, flow)
        log_exchange(exch, flow)

    def done(self):
        if self.report_file:
            self.dump_report()
            self.report_file.close()

    def dump_report(self):
        report_func = reports[self.output_format]
        self.report_file.seek(0)
        self.report_file.truncate()
        report_func(self.exchanges, self.report_file)


def construct_request(flow):
    version, headers, body = extract_message_basics(flow.request)
    scheme = decode(flow.request.scheme)
    method = decode(flow.request.method)

    # Authority-form and absolute-form requests in the tunnel
    # are simply rejected as errors by mitmproxy, closing the connection.
    target = decode(flow.request.path)

    if version == 'HTTP/2':
        pseudo_headers = httpolice.helpers.pop_pseudo_headers(headers)
        authority = pseudo_headers.get(':authority')
        has_host = any(k.lower() == 'host' for (k, v) in headers)
        if authority and not has_host and target.startswith('/'):
            # Reconstruct HTTP/2's equivalent of
            # the "absolute form" of request target (RFC 7540 Section 8.1.2.3).
            target = scheme + '://' + decode(authority) + target

    return httpolice.Request(scheme, method, target, version, headers, body)


def construct_response(flow):
    version, headers, body = extract_message_basics(flow.response)
    status = flow.response.status_code
    reason = decode(flow.response.reason)
    if version == 'HTTP/2':
        httpolice.helpers.pop_pseudo_headers(headers)
    return httpolice.Response(version, status, reason, headers, body)


def extract_message_basics(msg):
    version = decode(msg.http_version)
    if version == 'HTTP/2.0':
        version = 'HTTP/2'
    headers = [(decode(k), v) for (k, v) in msg.headers.fields]
    body = msg.raw_content
    return version, headers, body


def attach_report(exch, flow):
    buf = io.BytesIO()
    httpolice.text_report([exch], buf)
    if buf.getvalue():
        report = buf.getvalue().decode('utf-8')
        # It would be nicer to split this into separate metadata entries
        # for request and response, but since `flow.metadata` is a plain dict,
        # their order is random under Python 3.5 and sometimes request comes
        # after response. Also wrap in ``try...except`` because `flow.metadata`
        # is not public API yet.
        try:
            flow.metadata['HTTPolice report'] = ReprString(report)
        except Exception:          # pragma: no cover
            pass


def log_exchange(exch, flow):
    # Produce lines like "1 errors, 2 warnings" without hardcoding severities.
    severities = collections.Counter(notice.severity
                                     for msg in [exch.request] + exch.responses
                                     for notice in msg.notices)
    pieces = ['%d %ss' % (n, severity.name)
              for (severity, n) in sorted(severities.items(), reverse=True)
              if severity > httpolice.Severity.debug]
    if pieces:
        log_func = (mitmproxy.ctx.log.warn
                    if max(severities) >= httpolice.Severity.error
                    else mitmproxy.ctx.log.info)
        log_func('HTTPolice found %s in: %s %s - %d %s' % (
            ', '.join(pieces),
            flow.request.method, ellipsize(flow.request.path),
            flow.response.status_code, ellipsize(flow.response.reason),
        ))


def decode(s):
    if isinstance(s, bytes):
        return s.decode('iso-8859-1')
    else:
        return s


def ellipsize(s, max_length=40):
    if len(s) > max_length:
        ellipsis = '...'
        return s[:(max_length - len(ellipsis))] + ellipsis
    else:
        return s


class ReprString(str):

    # Currently mitmproxy displays ``repr()`` in details view, not ``str()``.
    # See also https://discourse.mitmproxy.org/t/extending-the-ui/359/5

    __slots__ = []

    def __repr__(self):
        return str(self)


def positive_int(x):
    x = int(x)
    if x < 1:
        raise ValueError('must be positive')
    return x


if __name__ == '__main__':
    # Print the path to this script,
    # for substitution into the mitmproxy command.
    print(__file__)
