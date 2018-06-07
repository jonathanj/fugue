from testtools import TestCase
from testtools.matchers import Contains, Equals, Is, MatchesListwise
from testtools.twistedsupport import succeeded

from fugue.adapters.nevow import nevow_adapter_resource
from fugue.interceptors import before
from fugue.interceptors.nevow import NEVOW_REQUEST
from fugue.test.interceptors.test_nevow import fakeNevowRequest
from fugue.test.util import depends_on


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
        self.assertThat(
            resource.renderHTTP(fakeNevowRequest()),
            succeeded(Equals(b'')))
        self.assertThat(
            requests,
            MatchesListwise([Contains(NEVOW_REQUEST)]))
