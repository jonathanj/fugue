from hyperlink import URL
from testtools import TestCase
from testtools.matchers import ContainsDict, Equals, Is
from twisted.web.server import Request

from fugue.interceptors.nevow import _nevow_request_to_request_map
from fugue.test.interceptors.test_nevow import fakeNevowRequest


def fakeTwistedRequest(*args, **kwargs):
    def _finish(request):
        def _inner():
            request.finish_count += 1
        request.finish_count = 0
        return _inner

    kwargs.setdefault('request', Request)
    request = fakeNevowRequest(*args, **kwargs)
    request.finish = _finish(request)
    return request


class TwistedRequestToRequestMapTests(TestCase):
    """
    Tests for `_nevow_request_to_request_map` on a Twisted request.
    """
    def test_basic(self):
        """
        Test basic request map keys.
        """
        request = fakeTwistedRequest(request_headers={
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
                'remote_addr': Equals(b'192.168.1.1'),
                'request_method': Equals(b'GET'),
                'server_name': Equals(b'10.0.0.1'),
                'server_port': Equals(80),
                'scheme': Equals(b'http'),
                'uri': Equals(URL.from_text(u'http://example.com/one'))}))
