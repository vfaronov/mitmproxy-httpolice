# -*- coding: utf-8; -*-

import collections
import io

import httpolice
import mitmproxy.ctx


__version__ = '0.7.0.dev1'


class MitmproxyHTTPolice:

    def response(self, flow):
        req = construct_request(flow)
        resp = construct_response(flow)
        exch = httpolice.Exchange(req, [resp])
        httpolice.check_exchange(exch)
        attach_report(exch, flow)
        log_exchange(exch, flow)



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
    report = buf.getvalue().decode('utf-8')
    for_request, for_response = parse_report(report)
    metadata_entries = [('Request notices', for_request),
                        ('Response notices', for_response)]
    try:
        for title, lines in metadata_entries:
            if lines:
                text = u'\n'.join(lines) + u'\n'
                flow.metadata[HashHack(title)] = ReprString(text)
    except Exception:               # pragma: no cover
        # `flow.metadata` is not public API, so could theoretically fail.
        pass


def parse_report(report):
    # `report` is a text report as produced by HTTPolice. From it, we want to
    # extract the notices (titles) for the request and for the response.
    # This may sound stupid: why not just make HTTPolice return them
    # in a structured form? But that would have to be a public API
    # (mitmproxy-HTTPolice doesn't use any private APIs from HTTPolice), and I
    # don't want to add public APIs to HTTPolice without a clear picture of
    # how and by whom they will be used. I want some sort of "JSON report"
    # in HTTPolice eventually, but I don't know the details yet. So for now,
    # let's just parse semi-structured text -- a great Unix tradition.
    for_request, for_response = [], []
    target = for_request
    for line in report.splitlines():
        if line.startswith('------------ request:'):
            target = for_request
        elif line.startswith('------------ response:'):
            target = for_response
        else:
            target.append(line)
    return for_request, for_response


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
        log_func('HTTPolice: %s in: %s %s ← %d' % (
            ', '.join(pieces),
            flow.request.method, ellipsize(flow.request.path),
            flow.response.status_code,
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


class HashHack(str):

    # Under Python 3.5, keys of `flow.metadata` (which is a plain `dict`)
    # are iterated over, and hence displayed in the UI, in random order,
    # depending on the hash seed. This may cause response notices to be shown
    # before request notices. Work around this with a hack that forces
    # the desired hash for the string. This may theoretically not work under
    # some unusual Python implementation, but if it doesn't work, all we get
    # is a slightly inconvenient UI. The alternative is to lump the entire
    # report into one metadata entry, which looks ugly for everyone.

    __slots__ = []

    def __hash__(self):
        return 1 if u'request' in self.lower() else 2


class ReprString(str):

    # Currently mitmproxy displays ``repr()`` in details view, not ``str()``.
    # See also https://discourse.mitmproxy.org/t/extending-the-ui/359/5

    __slots__ = []

    def __repr__(self):
        return str(self)


addons = [MitmproxyHTTPolice()]


if __name__ == '__main__':
    # Print the path to this script,
    # for substitution into the mitmproxy command.
    print(__file__)
