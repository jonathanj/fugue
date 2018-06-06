from pyrsistent import field, PRecord

from fugue._keys import REQUEST, RESPONSE


class Interceptor(PRecord):
    """
    An interceptor.

    The three stages of execution are `enter`, `leave` and `error`. Each stage
    is invoked with the context (and an `Error`, for the error stage) and is
    expected to return a context or a `Deferred` that returns a context.
    """
    name = field(mandatory=True, type=(str, unicode))
    enter = field(initial=None)
    leave = field(initial=None)
    error = field(initial=None)


def _interceptor_func_name(*fs):
    """
    Derive an interceptor name from one or more functions.
    """
    return u' & '.join(repr(f) for f in fs)


def error_handler(f, name=None):
    """
    An interceptor which calls a function during the error stage.

    :param f: Callable to be called with a context and an error, producing a
    new context.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return Interceptor(
        name=name or _interceptor_func_name(f),
        error=f)


def before(f, name=None):
    """
    An interceptor which calls a function during the enter stage.

    :param f: Callable.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return Interceptor(
        name=name or _interceptor_func_name(f),
        enter=lambda ctx: f(ctx))


def after(f, name=None):
    """
    An interceptor which calls a function during the leave stage.

    :param f: Callable.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return Interceptor(
        name=name or _interceptor_func_name(f),
        leave=lambda ctx: f(ctx))


def around(f1, f2, name=None):
    """
    An interceptor which calls a function during the enter stage and another
    function during the leave stage.

    :param f1: Callable.
    :param f2: Callable.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return Interceptor(
        name=name or _interceptor_func_name(f1, f2),
        enter=f1,
        leave=f2)


def handler(f, name=None):
    """
    An interceptor which calls a function on the context `REQUEST` value and
    sets result as the context `RESPONSE` value.

    :param f: Callable.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return before(
        lambda ctx: ctx.set(RESPONSE, f(ctx.get(REQUEST))),
        name=name or _interceptor_func_name(f))


def middleware(f1, f2, name=None):
    """
    An interceptor which calls a function on the context `REQUEST` value and
    another function on the context `RESPONSE` value.

    :param f1: Callable.
    :param f2: Callable.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return around(
        (None
         if f1 is None else
         lambda context: context.transform([REQUEST], f1)),
        (None
         if f2 is None else
         lambda context: context.transform([RESPONSE], f2)),
        name=name or _interceptor_func_name(f1, f2))


def on_request(f, name=None):
    """
    An interceptor which updates the context value of `REQUEST` during the
    enter stage.

    :param f: Callable to update the request.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return middleware(f, None, name=name)


def on_response(f, name=None):
    """
    An interceptor which updates the context value of `RESPONSE` during the
    leave stage.

    :param f: Callable to update the response.
    :param unicode name: Interceptor name.
    :rtype: Interceptor
    """
    return middleware(None, f, name=name)


__all__ = [
    'error_handler', 'before', 'after', 'around', 'handler', 'middleware',
    'on_request', 'on_response',
    ]
