import types
from functools import partial


def namespace(prefix):
    """
    Return a function for prefixing names, a crude namespacing mechanism.

    A good idea is to pass a module's ``__name__`` value as the prefix, since
    this will create relatively conflict-free names that are also human
    readable.

    :rtype: ``Callable[[str], str]``
    """
    return lambda name: '{}/{}'.format(prefix, name)


def identity(x):
    """
    The identity function.
    """
    return x


def every_pred(*preds):
    """
    Create a function that returns true if all ``preds`` return true against
    the provided arguments.

    :param *preds: Predicates.
    :rtype: Callable[[Any], bool]
    """
    return lambda *a, **kw: all(pred(*a, **kw) for pred in preds)


def callable_name(f):
    """
    Make a best effort attempt to name some callable.

    :param Callable f: A partial, lambda, function or object implementing
    ``__call_``.
    :rtype: str
    """
    if isinstance(f, partial):
        return callable_name(f.func)
    elif callable(f):
        if isinstance(f, (types.FunctionType, types.MethodType)):
            name = getattr(f, 'func_name', None)
        elif isinstance(f, types.TypeType):
            name = getattr(f, '__name__', None)
        else:
            # Probably an instance with a `__call__` method?
            name = getattr(type(f), '__name__', None)
        return name or repr(f)
    else:
        raise TypeError('Not a callable', f)


def url_path(url):
    """
    Construct a path string for a Hyperlink URL.

    :type url: hyperlink.URL
    :param url: URL.
    :rtype: unicode
    """
    return (u'/' if url.rooted else u'') + u'/'.join(url.path)


def constantly(result):
    """
    Return a function that accepts any arguments but always returns ``result``.
    """
    def _constantly(*a, **kw):
        return result
    return _constantly
