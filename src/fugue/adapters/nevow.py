from __future__ import absolute_import

from pyrsistent import pmap, v

from fugue.chain import execute
from fugue.interceptors.nevow import nevow, NEVOW_REQUEST


_NevowAdapterResource = None


def _import_nevow():
    """
    Import Nevow and define `_NevowAdapterResource`.

    This is to avoid:

      - Requiring Nevow on importing the module;
      - Masking the import error if Nevow is not installed but
        `nevow_adapter_resource` is called.
      - Definining `_NevowAdapterResource` more than once.
    """
    global _NevowAdapterResource
    if _NevowAdapterResource is not None:
        return

    from nevow.inevow import IResource, IRequest
    from zope.interface import implementer

    @implementer(IResource)
    class _NevowAdapterResource(object):
        def __init__(self, interceptors):
            self._interceptors = interceptors

        def locateChild(self, ctx, segments):
            return self, ()

        def renderHTTP(self, nevow_ctx):
            context = pmap({
                NEVOW_REQUEST: IRequest(nevow_ctx),
            })
            d = execute(context, v(nevow()) + self._interceptors)
            d.addCallback(lambda _: b'')
            return d


def nevow_adapter_resource(interceptors=v()):
    """
    Create a Nevow ``IResource`` that executes a context and avoids as much
    Nevow machinery as possible.

    A ~`fugue.interceptors.nevow.nevow` interceptor will be attached to the
    front of the queue to facilitate the interaction with Nevow.
    """
    _import_nevow()
    return _NevowAdapterResource(interceptors)


__all__ = ['nevow_adapter_resource']
