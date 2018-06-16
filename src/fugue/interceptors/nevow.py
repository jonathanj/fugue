from __future__ import absolute_import

import cgi

from hyperlink import URL
from pyrsistent import freeze, m
from twisted.internet.defer import Deferred, succeed

from fugue._keys import REQUEST, RESPONSE
from fugue.interceptors.basic import Interceptor
from fugue.util import namespace, url_path


_ns = namespace(__name__)
NEVOW_REQUEST = _ns('request')


_noop = lambda *a, **kw: None


def _get_headers(headers, name, default=None):
    """
    All values for a header by name.
    """
    return headers.getRawHeaders(name, [default])


def _get_first_header(headers, name, default=None):
    """
    Only the first value for a header by name.
    """
    return _get_headers(headers, name, default)[0]


def _get_content_type(headers, default=b'application/octet-stream'):
    """
    Parse the ``Content-Type`` header into the content type and character
    encoding.
    """
    content_type = _get_first_header(headers, b'content-type', default)
    _, options = cgi.parse_header(content_type)
    return content_type, options.get('charset')


def _nevow_request_to_request_map(req):
    """
    Convert a Nevow request object into an immutable request map.
    """
    headers = req.requestHeaders
    content_type, character_encoding = _get_content_type(headers)
    iri = URL.from_text(req.uri.decode('utf-8')).to_iri()
    host = _get_first_header(headers, b'host').decode('utf-8')
    scheme = u'https' if req.isSecure() else u'http'
    if u':' in host:
        host, port = host.split(u':', 1)
        port = int(port)
    else:
        port = {
            u'https': 443,
            u'http': 80}.get(scheme)
    return m(
        body=req.content,
        content_type=content_type,
        content_length=_get_first_header(headers, b'content-length'),
        character_encoding=character_encoding,
        headers=freeze(dict(headers.getAllRawHeaders())),
        remote_addr=req.getClientIP(),
        request_method=req.method,
        server_name=req.getRequestHostname(),
        server_port=req.host.port,
        scheme=scheme,
        #ssl_client_cert=XXX,
        uri=iri,
        #query_string
        path_info=url_path(iri),
        protocol=getattr(req, 'clientproto', None))


def _send_response(context, request_key, finish):
    """
    Write a response to the network.
    """
    req = context[request_key]
    response = context[RESPONSE]
    req.setResponseCode(response['status'])
    for k, v in response.get('headers', []):
        req.responseHeaders.setRawHeaders(k, v)
    req.write(response['body'])
    finish(context)


def _send_error(context, message, request_key, finish):
    """
    Write an error response to the network.
    """
    _send_response(
        context.set(
            RESPONSE,
            m(status=500,
              body=message)),
        request_key,
        finish)


def _enter_nevow(request_key):
    """
    Enter stage factory for Nevow interceptor.

    Extract information from a Nevow request into an immutable data structure.
    """
    def _enter_nevow_inner(context):
        return context.set(
            REQUEST,
            _nevow_request_to_request_map(context[request_key]))
    return _enter_nevow_inner


def _leave_nevow(request_key, finish=_noop):
    """
    Leave stage factory for Nevow interceptor.

    Set the HTTP status code, any response headers and write the body (`bytes`
    or `Deferred`) to the network. If ``RESPONSE`` is nonexistent, an HTTP 500
    error is written to the network instead.
    """
    def _leave_nevow_inner(context):
        def _leave(body, context):
            context = context.set('body', body)
            _send_response(context, request_key, finish)
            return context

        response = context.get(RESPONSE)
        if response is None:
            _send_error(
                context, 'Internal server error: no response', request_key, finish)
            return succeed(context)
        body = response.get('body')
        d = body if isinstance(body, Deferred) else succeed(body)
        d.addCallback(_leave, context)
        return d
    return _leave_nevow_inner


def _error_nevow(request_key, finish=_noop):
    """
    Error stage factory for Nevow interceptor.
    """
    def _error_nevow_inner(context, error):
        # XXX: log error
        _send_error(context, 'Internal server error: exception', request_key, finish)
        return context
    return _error_nevow_inner


def nevow():
    """
    An interceptor that converts a Nevow request into a standard request map on
    enter and writes the response back to Nevow on leave.

    The Nevow request is expected to exist at the context key `NEVOW_REQUEST`.
    """
    return Interceptor(
        name='nevow',
        enter=_enter_nevow(NEVOW_REQUEST),
        leave=_leave_nevow(NEVOW_REQUEST),
        error=_error_nevow(NEVOW_REQUEST))


__all__ = ['nevow', 'NEVOW_REQUEST']
