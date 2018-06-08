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
