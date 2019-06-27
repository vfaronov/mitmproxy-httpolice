import collections
import email.utils
from http import HTTPStatus
import io
import typing

import httpolice
from mitmproxy import ctx
import mitmproxy.flow
import mitmproxy.http
import mitmproxy.net.http
import mitmproxy.types


__version__ = '0.9.0'


class MitmproxyHTTPolice:

    def __init__(self):
        self.last_report = None

    def load(self, loader):
        loader.add_option(
            name='httpolice_silence',
            # ``typing.Sequence[int]`` would be better, but is not supported.
            typespec=typing.Sequence[str],
            default=[],
            help='Silence these HTTPolice notice IDs.',
        )
        loader.add_option(
            name='httpolice_mark',
            # Could make this a ``typing.Optional[str]``, but
            # that doesn't work well with the interactive editors,
            # so make "disable" an explicit choice.
            typespec=str,
            choices=[''] + [sev.name for sev in httpolice.Severity],
            default='',
            help=
                'Mark flows where HTTPolice found notices of this severity '
                'or higher (empty to disable).'
        )

    def request(self, flow):
        if flow.request.path == '/+httpolice/':
            flow.response = self.serve_report()

    def response(self, flow):
        exch = flow_to_exchange(flow)
        attach_report(exch, flow)
        mark_exchange(exch, flow)
        log_exchange(exch, flow)

    @mitmproxy.command.command('httpolice.report.html')
    def html_report(self,
                    flows: typing.Sequence[mitmproxy.flow.Flow],
                    path: mitmproxy.types.Path) -> None:
        """Produce an HTTPolice report (HTML) on flows."""
        self.report(flows, httpolice.html_report, path)

    @mitmproxy.command.command('httpolice.report.text')
    def text_report(self,
                    flows: typing.Sequence[mitmproxy.flow.Flow],
                    path: mitmproxy.types.Path) -> None:
        """Produce an HTTPolice report (text) on flows."""
        self.report(flows, httpolice.text_report, path)

    def report(self, flows, report_func, path):
        exchanges = (flow_to_exchange(flow) for flow in flows)
        if path == '-':
            buf = io.BytesIO()
            report_func(exchanges, buf)
            self.last_report = buf.getvalue()
            ctx.log.alert(
                f'HTTPolice: saved report on {len(flows)} flows in memory')
        else:
            with open(path, 'wb') as f:
                report_func(exchanges, f)
            ctx.log.alert(
                f'HTTPolice: wrote report on {len(flows)} flows to {path}')

    def serve_report(self):
        if self.last_report is None:
            status_code = HTTPStatus.NOT_FOUND.value
            content = (
                f'<!DOCTYPE html><p>No report has been <a href="'
                f'https://mitmproxy-httpolice.readthedocs.io/en/{__version__}/'
                f'walkthrough.html#inmemory">produced</a> yet.</p>'
            ).encode('utf-8')
        else:
            status_code = HTTPStatus.OK.value
            content = self.last_report
        headers = {
            'Date': email.utils.formatdate(usegmt=True),
            'Content-Type': (
                'text/html; charset=utf-8' if content.startswith(b'<!')
                else 'text/plain; charset=utf-8'
            ),
            'Cache-Control': 'no-store',
        }
        return mitmproxy.http.HTTPResponse.wrap(
            mitmproxy.net.http.Response.make(status_code, content, headers),
        )


def flow_to_exchange(flow):
    req = construct_request(flow)
    resp = construct_response(flow)
    exch = httpolice.Exchange(req, [resp] if resp else [])
    exch.silence([int(id_) for id_ in ctx.options.httpolice_silence])
    httpolice.check_exchange(exch)
    return exch


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
    if flow.response is None:
        return None
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
    for title, lines in [('HTTPolice: request', for_request),
                         ('HTTPolice: response', for_response)]:
        if lines:
            text = u'\n'.join(lines) + u'\n'
            try:
                # If this script is being run on a flow previously loaded
                # from file, `flow.metadata` might already contain our keys
                # in the wrong order. Reinsert them instead of just updating.
                flow.metadata.pop(title, None)
                flow.metadata[title] = ReprString(text)
            except Exception:
                # `flow.metadata` is not public API,
                # so could theoretically fail.
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


def mark_exchange(exch, flow):
    if ctx.options.httpolice_mark:
        mark_severity = httpolice.Severity[ctx.options.httpolice_mark]
        if any(notice.severity >= mark_severity
               for msg in [exch.request] + exch.responses
               for notice in msg.notices):
            flow.marked = True


def log_exchange(exch, flow):
    # Produce lines like "1 errors, 2 comments" without hardcoding severities.
    severities = collections.Counter(notice.severity
                                     for msg in [exch.request] + exch.responses
                                     for notice in msg.notices)
    pieces = [f'{n} {severity.name}s'
              for (severity, n) in sorted(severities.items(), reverse=True)
              if severity > httpolice.Severity.debug]
    if pieces:
        log_func = (ctx.log.warn
                    if max(severities) >= httpolice.Severity.error
                    else ctx.log.info)
        log_func('HTTPolice: {0} in: {1} {2} ← {3}'.format(
            ', '.join(pieces),
            flow.request.method, ellipsize(flow.request.path),
            flow.response.status_code,
        ))


def decode(s):
    if isinstance(s, bytes):
        return s.decode('iso-8859-1')
    return s


def ellipsize(s, max_length=40):
    if len(s) <= max_length:
        return s
    ellipsis = '...'
    return s[:(max_length - len(ellipsis))] + ellipsis


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
