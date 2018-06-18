from __future__ import absolute_import

from pyrsistent import pmap, v
from twisted.web.resource import IResource
from twisted.web.server import NOT_DONE_YET
from zope.interface import implementer

from fugue.chain import execute
from fugue.interceptors.twisted import twisted, TWISTED_REQUEST


@implementer(IResource)
class _TwistedAdapterResource(object):
    isLeaf = True

    def __init__(self, interceptors):
        self._interceptors = interceptors

    def render(self, request):
        context = pmap({TWISTED_REQUEST: request})
        execute(context, v(twisted()) + self._interceptors)
        return NOT_DONE_YET

    def putChild(self, path, child):
        raise NotImplementedError()

    def getChildWithDefault(self, path, request):
        # When this resource is the root resource, for example when using
        # `twistd web --resource-script`, this function will be called despite
        # being a leaf resource.
        return self


def twisted_adapter_resource(interceptors=v()):
    """
    Create a Twisted ``IResource`` that executes a context and avoids as much
    Twisted machinery as possible.

    A ~`fugue.interceptors.twisted.twisted` interceptor will be attached to the
    front of the queue to facilitate the interaction with Twisted.
    """
    return _TwistedAdapterResource(interceptors)


__all__ = ['twisted_adapter_resource']
