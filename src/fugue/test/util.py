from testtools import try_import


def depends_on(*names):
    """
    Decorate a test method with skip condition that all of ``names`` are
    importable.
    """
    def _depends_on(f):
        def _depends_on_inner(self, *a, **kw):
            for name in names:
                if try_import(name) is None:
                    self.skipTest('"{}" dependency missing'.format(name))
            return f(self, *a, **kw)
        return _depends_on_inner
    return _depends_on
