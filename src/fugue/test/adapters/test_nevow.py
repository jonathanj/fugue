from pyrsistent import freeze, m
from testtools import TestCase
from testtools.matchers import Contains, Equals, Is, MatchesListwise
from testtools.twistedsupport import succeeded
from twisted.python.failure import Failure

from fugue.adapters.nevow import nevow_adapter_resource
from fugue.interceptors import before, handler
from fugue.interceptors.nevow import NEVOW_REQUEST
from fugue.test.interceptors.test_nevow import fake_nevow_request
from fugue.test.util import depends_on
from fugue.util import constantly


def ok(body, headers=m(), status=200):
    return m(status=status, body=body, headers=freeze(headers))


class NevowAdapterResourceTests(TestCase):
    """
    Tests for `nevow_adapter_resource`.
    """
    @depends_on('nevow')
    def test_leaf(self):
        """
        The resource identifies as a leaf.
        """
        resource = nevow_adapter_resource()
        self.assertThat(
            resource.locateChild(None, None),
            MatchesListwise([
                Is(resource),
                Equals(())]))

    @depends_on('nevow')
    def test_nevow_request(self):
        """
        Rendering the resource returns a successful deferred and inserted a
        `NEVOW_REQUEST` value into the context.
        """
        def _spy(res):
            def _spy_inner(context):
                res.append(context)
                return context
            return before(_spy_inner)

        requests = []
        resource = nevow_adapter_resource([_spy(requests)])
        req = fake_nevow_request()
        self.assertThat(
            resource.renderHTTP(req),
            succeeded(Equals(b'')))
        self.assertThat(
            requests,
            MatchesListwise([Contains(NEVOW_REQUEST)]))

    @depends_on('nevow')
    def test_body_status(self):
        """
        Write a response body and status to the Nevow request.
        """
        resource = nevow_adapter_resource(
            [handler(lambda _: ok(b'Hello world!', status=201))])
        req = fake_nevow_request()
        self.assertThat(
            resource.renderHTTP(req),
            succeeded(Equals(b'')))
        self.assertThat(
            req.code,
            Equals(201))
        req.channel.transport.written.seek(0)
        self.assertThat(
            req.channel.transport.written.read(),
            Contains(b'Hello world!'))

    @depends_on('nevow')
    def test_response_headers(self):
        """
        Write response headers to the Nevow request.
        """
        resource = nevow_adapter_resource(
            [handler(lambda _: ok(b'', headers={b'X-Foo': [b'foo'],
                                                b'X-Bar': b'bar'}))])
        req = fake_nevow_request()
        self.assertThat(
            resource.renderHTTP(req),
            succeeded(Equals(b'')))
        self.assertThat(
            req.responseHeaders.getRawHeaders(b'X-Foo'),
            Equals([b'foo']))
        self.assertThat(
            req.responseHeaders.getRawHeaders(b'X-Bar'),
            Equals([b'bar']))

    @depends_on('nevow')
    def test_error(self):
        """
        If an exception is unhandled, set the response body and status
        accordingly.
        """
        f = Failure(RuntimeError('Nope'))
        resource = nevow_adapter_resource([before(constantly(f))])
        req = fake_nevow_request()
        self.assertThat(
            resource.renderHTTP(req),
            succeeded(Equals(b'')))
        req.channel.transport.written.seek(0)
        self.assertThat(
            req.channel.transport.written.read(),
            Contains(b'Internal server error: exception'))
        self.assertThat(
            req.code,
            Equals(500))
