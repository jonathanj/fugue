from testtools import TestCase
from testtools.matchers import Contains, Equals, MatchesListwise
from twisted.web.server import NOT_DONE_YET

from fugue.adapters.twisted import twisted_adapter_resource
from fugue.interceptors import before
from fugue.interceptors.twisted import TWISTED_REQUEST
from fugue.test.interceptors.test_twisted import fake_twisted_request


class TwistedAdapterResourceTests(TestCase):
    """
    Tests for `twisted_adapter_resource`.
    """
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
