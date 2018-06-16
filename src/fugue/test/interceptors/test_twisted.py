import itertools

from hyperlink import URL
from testtools import TestCase
from testtools.matchers import ContainsDict, Equals, Is
from twisted.web.server import Request

from fugue.interceptors.nevow import _nevow_request_to_request_map
from fugue.test.interceptors.test_nevow import fake_nevow_request


def fake_twisted_request(*args, **kwargs):
    """
    Create a fake Twisted `Request` instance for the purposes of testing.
    """
    kwargs.setdefault(
        'Request', lambda channel: Request(channel=channel, queued=False))
    request = fake_nevow_request(*args, **kwargs)
    request.finish = lambda: next(request.finish.counter)
    request.finish.counter = itertools.count()
    return request


class TwistedRequestToRequestMapTests(TestCase):
    """
    Tests for `_nevow_request_to_request_map` on a Twisted request.
    """
    def test_basic(self):
        """
        Test basic request map keys.
        """
        request = fake_twisted_request(request_headers={
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
