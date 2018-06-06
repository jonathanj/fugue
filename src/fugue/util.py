def namespace(prefix):
    """
    Return a function for prefixing names, a crude namespacing mechanism.
    """
    return lambda name: '{}/{}'.format(prefix, name)


def identity(x):
    """
    The identity function.
    """
    return x
