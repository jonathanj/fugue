from hyperlink import URL
from nevow.appserver import NevowRequest
from testtools import TestCase
from testtools.matchers import AfterPreprocessing as After
from testtools.matchers import ContainsDict, Equals, Is
from twisted.internet.address import IPv4Address
from twisted.test.proto_helpers import StringTransport

from fugue.interceptors.nevow import _nevow_request_to_request_map


def fakeNevowRequest(method='GET', body=b'', is_secure=False,
                     uri=b'http://example.com/one', request_headers=None):
    """
    Create a fake `NevowRequest` instance for the purposes of testing.
    """
    class FakeChannel(object):
        def __init__(self, transport):
            self.transport = transport
            self.isSecure = lambda: is_secure
            self.getPeer = transport.getPeer
            self.getHost = transport.getHost

    port = 443 if is_secure else 80
    channel = FakeChannel(StringTransport(
        peerAddress=IPv4Address('TCP', '192.168.0.1', 54321),
        hostAddress=IPv4Address('TCP', '10.0.0.1', port)))
    request = NevowRequest(channel=channel)
    request.method = method
    request.uri = uri
    request.client = channel.transport.getPeer()
    request.host = channel.transport.getHost()
    content_length = len(body)
    request.requestHeaders.setRawHeaders('content-length', [content_length])
    if request_headers:
        for k, v in request_headers.items():
            request.requestHeaders.setRawHeaders(k, v)
    request.gotLength(content_length)
    request.content.write(body)
    request.content.seek(0)
    return request


class NevowRequestToRequestMapTests(TestCase):
    """
    Tests for `_nevow_request_to_request_map`.
    """
    def test_basic(self):
        """
        Test basic request map keys.
        """
        request = fakeNevowRequest(request_headers={
            b'x-foo': [b'bar'],
        })
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'content_type': Equals(b'application/octet-stream'),
                'content_length': Equals(0),
                'character_encoding': Is(None),
                'headers': Equals({b'Content-Length': [0],
                                   b'X-Foo': [b'bar']}),
                'remote_addr': Equals(b'192.168.0.1'),
                'request_method': Equals(b'GET'),
                'server_name': Equals(b'10.0.0.1'),
                'server_port': Equals(80),
                'scheme': Equals(b'http'),
                'uri': Equals(URL.from_text(u'http://example.com/one'))}))

    def test_scheme(self):
        """
        ``scheme`` is set according to whether the request is secure.
        """
        self.assertThat(
            _nevow_request_to_request_map(
                fakeNevowRequest(is_secure=False)),
            ContainsDict({
                'scheme': Equals(b'http')}))
        self.assertThat(
            _nevow_request_to_request_map(
                fakeNevowRequest(is_secure=True)),
            ContainsDict({
                'scheme': Equals(b'https')}))

    def test_content_type(self):
        """
        ``Content-Type`` header is extracted.
        """
        request = fakeNevowRequest(request_headers={
            b'content-type': [b'text/plain;charset=utf-8'],
        })
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'content_type': Equals(b'text/plain;charset=utf-8')}))

    def test_character_encoding(self):
        """
        Character encoding is extracted from ``Content-Type``, if available.
        """
        request = fakeNevowRequest(request_headers={
            b'content-type': [b'text/plain;charset=utf-8'],
        })
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'character_encoding': Equals(b'utf-8')}))

    def test_body(self):
        """
        ``body`` is a file-like containing the request content.
        """
        request = fakeNevowRequest(body=b'hello')
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'body': After(
                    lambda x: x.read(),
                    Equals(b'hello')),
                'content_length': Equals(5)}))
