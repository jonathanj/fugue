from hyperlink import URL
from testtools import TestCase, try_import
from testtools.matchers import AfterPreprocessing as After
from testtools.matchers import ContainsDict, Equals, Is
from twisted.web.test.requesthelper import DummyChannel

from fugue.interceptors.nevow import _nevow_request_to_request_map
from fugue.test.util import depends_on
from fugue.util import url_path


NevowRequest = try_import('nevow.appserver.NevowRequest')


def fake_nevow_request(method='GET', body=b'', is_secure=False,
                       uri=b'http://example.com/one', request_headers=None,
                       Request=NevowRequest):
    """
    Create a fake `NevowRequest` instance for the purposes of testing.
    """
    uri = URL.from_text(uri.decode('utf-8')).to_uri()
    channel = DummyChannel()
    if is_secure:
        channel.transport = DummyChannel.SSL()
    request = Request(channel=channel)
    request.method = method
    request.uri = url_path(uri)
    request.clientproto = b'HTTP/1.1'
    request.client = channel.transport.getPeer()
    content_length = len(body)
    request.requestHeaders.setRawHeaders(
        'host', [uri.authority().encode('utf-8')])
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
    @depends_on('nevow')
    def test_basic(self):
        """
        Test basic request map keys.
        """
        request = fake_nevow_request(request_headers={
            b'x-foo': [b'bar'],
        })
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'content_type': Equals(b'application/octet-stream'),
                'content_length': Equals(0),
                'character_encoding': Is(None),
                'headers': Equals({b'Content-Length': [0],
                                   b'X-Foo': [b'bar'],
                                   b'Host': [b'example.com']}),
                'remote_addr': Equals(b'192.168.1.1'),
                'request_method': Equals(b'GET'),
                'server_name': Equals(b'example.com'),
                'server_port': Equals(80),
                'scheme': Equals(b'http'),
                'uri': Equals(URL.from_text(u'/one'))}))

    @depends_on('nevow')
    def test_non_standard_port(self):
        """
        Parse a non-standard port from the ``Host`` header.
        """
        request = fake_nevow_request(uri=u'http://example.com:5144/')
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'headers': ContainsDict(
                    {b'Host': Equals([b'example.com:5144'])}),
                'server_name': Equals(b'example.com'),
                'server_port': Equals(5144)}))


    @depends_on('nevow')
    def test_scheme(self):
        """
        ``scheme`` is set according to whether the request is secure.
        """
        self.assertThat(
            _nevow_request_to_request_map(
                fake_nevow_request(is_secure=False)),
            ContainsDict({
                'scheme': Equals(b'http')}))
        self.assertThat(
            _nevow_request_to_request_map(
                fake_nevow_request(is_secure=True)),
            ContainsDict({
                'scheme': Equals(b'https')}))

    @depends_on('nevow')
    def test_content_type(self):
        """
        ``Content-Type`` header is extracted.
        """
        request = fake_nevow_request(request_headers={
            b'content-type': [b'text/plain;charset=utf-8'],
        })
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'content_type': Equals(b'text/plain;charset=utf-8')}))

    @depends_on('nevow')
    def test_character_encoding(self):
        """
        Character encoding is extracted from ``Content-Type``, if available.
        """
        request = fake_nevow_request(request_headers={
            b'content-type': [b'text/plain;charset=utf-8'],
        })
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'character_encoding': Equals(b'utf-8')}))

    @depends_on('nevow')
    def test_body(self):
        """
        ``body`` is a file-like containing the request content.
        """
        request = fake_nevow_request(body=b'hello')
        self.assertThat(
            _nevow_request_to_request_map(request),
            ContainsDict({
                'body': After(
                    lambda x: x.read(),
                    Equals(b'hello')),
                'content_length': Equals(5)}))
