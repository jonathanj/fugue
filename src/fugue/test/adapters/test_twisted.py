from testtools import ExpectedException, TestCase
from testtools.matchers import Contains, Equals, Is, MatchesListwise
from twisted.python.failure import Failure
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from fugue.adapters.twisted import twisted_adapter_resource
from fugue.interceptors import before, handler
from fugue.interceptors.twisted import TWISTED_REQUEST
from fugue.test.adapters.test_nevow import ok
from fugue.test.interceptors.test_twisted import fake_twisted_request
from fugue.util import constantly


class TwistedAdapterResourceTests(TestCase):
    """
    Tests for `twisted_adapter_resource`.
    """
    def test_leaf(self):
        """
        The resource identifies as a leaf, it cannot be given child resources
        and cannot locate them either.
        """
        resource = twisted_adapter_resource()
        with ExpectedException(NotImplementedError):
            resource.putChild('path', Resource())
        self.assertThat(
            resource.getChildWithDefault('path', fake_twisted_request()),
            Is(resource))

    def test_twisted_request(self):
        """
        Rendering the resource returns a successful deferred, inserts a
        `TWISTED_REQUEST` value into the context and calls ``finish`` on the
        request.
        """
        def _spy(res):
            def _spy_inner(context):
                res.append(context)
                return context
            return before(_spy_inner)

        requests = []
        request = fake_twisted_request()
        resource = twisted_adapter_resource([_spy(requests)])
        self.assertThat(
            resource.render(request),
            Equals(NOT_DONE_YET))
        self.assertThat(
            requests,
            MatchesListwise([Contains(TWISTED_REQUEST)]))
        self.assertThat(
            next(request.finish.counter),
            Equals(1))

    def test_body_status(self):
        """
        Write a response body and status to the Twisted request.
        """
        resource = twisted_adapter_resource(
            [handler(lambda _: ok(b'Hello world!', status=201))])
        req = fake_twisted_request()
        self.assertThat(
            resource.render(req),
            Equals(NOT_DONE_YET))
        self.assertThat(
            req.code,
            Equals(201))
        req.channel.transport.written.seek(0)
        self.assertThat(
            req.channel.transport.written.read(),
            Contains(b'Hello world!'))

    def test_response_headers(self):
        """
        Write response headers to the Twisted request.
        """
        resource = twisted_adapter_resource(
            [handler(lambda _: ok(b'', headers={b'X-Foo': [b'foo'],
                                                b'X-Bar': b'bar'}))])
        req = fake_twisted_request()
        self.assertThat(
            resource.render(req),
            Equals(NOT_DONE_YET))
        self.assertThat(
            req.responseHeaders.getRawHeaders(b'X-Foo'),
            Equals([b'foo']))
        self.assertThat(
            req.responseHeaders.getRawHeaders(b'X-Bar'),
            Equals([b'bar']))

    def test_error(self):
        """
        If an exception is unhandled, set the response body and status
        accordingly.
        """
        f = Failure(RuntimeError('Nope'))
        resource = twisted_adapter_resource([before(constantly(f))])
        req = fake_twisted_request()
        self.assertThat(
            resource.render(req),
            Equals(NOT_DONE_YET))
        req.channel.transport.written.seek(0)
        self.assertThat(
            req.channel.transport.written.read(),
            Contains(b'Internal server error: exception'))
        self.assertThat(
            req.code,
            Equals(500))
