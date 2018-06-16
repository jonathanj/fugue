from functools import partial

from hyperlink import URL
from testtools import ExpectedException, TestCase
from testtools.matchers import (
    AllMatch, Equals, Is, MatchesListwise, MatchesStructure)

from fugue.util import (
    callable_name, constantly, every_pred, namespace, url_path)


class NamespaceTests(TestCase):
    """
    Tests for `namespace`.
    """
    def test_namespace(self):
        """
        Create a function that prefixes names.
        """
        ns = namespace(__name__)
        self.assertThat(
            ns('foo'),
            Equals(__name__ + '/foo'))


class EveryPredTests(TestCase):
    """
    Tests for `every_pred`.
    """
    def test_empty(self):
        """
        Default to a ``True`` result when there are no predicates.
        """
        self.assertThat(every_pred()(), Is(True))

    def test_args(self):
        """
        Pass arguments through to the predicates.
        """
        def _capture(result):
            def _capture_inner(*a, **kw):
                called.append((a, kw))
                return result
            called = []
            return _capture_inner, called

        capture, called = _capture(True)
        self.assertThat(
            every_pred(capture, capture)(1, b=3),
            Is(True))
        self.assertThat(
            called,
            MatchesListwise([
                Equals(((1,), dict(b=3))),
                Equals(((1,), dict(b=3)))]))

    def test_true(self):
        """
        Returns ``True`` if all predicates return true values.
        """
        true = lambda: True
        self.assertThat(
            every_pred(true, true)(),
            Is(True))

    def test_false(self):
        """
        Returns ``False`` if any predicate returns a false value.
        """
        false = lambda: False
        true = lambda: True
        self.assertThat(
            every_pred(true, false)(),
            Is(False))


class CallableNameTests(TestCase):
    """
    Tests for `callable_name`.
    """
    def test_method(self):
        """
        Methods.
        """
        self.assertThat(
            [callable_name(partial(self.test_method)),
             callable_name(self.test_method)],
            AllMatch(Equals(self.test_method.func_name)))

    def test_function(self):
        """
        Functions
        """
        def _function():
            pass  # pragma: no cover
        self.assertThat(
            [callable_name(partial(_function)),
             callable_name(_function)],
            AllMatch(Equals(_function.func_name)))

    def test_lambda(self):
        """
        Lambdas.
        """
        lam = lambda: None  # pragma: no cover
        self.assertThat(
            [callable_name(partial(lam)),
            callable_name(lam)],
            AllMatch(Equals(lam.func_name)))

    def test_callable(self):
        """
        Callables.
        """
        class call(object):
            def __call__(self):
                pass  # pragma: no cover

        c = call()
        self.assertThat(
            [callable_name(partial(call)),
             callable_name(call),
             callable_name(partial(c)),
             callable_name(c)],
            AllMatch(Equals(call.__name__)))

    def test_not_callable(self):
        """
        Raise `TypeError` if the argument is not a callable.
        """
        f = 42
        matcher = MatchesStructure(
            args=Equals(('Not a callable', f)))
        with ExpectedException(TypeError, matcher):
            callable_name(f)


class URLPathTests(TestCase):
    """
    Tests for `url_path`.
    """
    def test_rooted_empty(self):
        """
        Rooted empty path.
        """
        self.assertThat(
            [url_path(URL.from_text(u'http://example.com/')),
             url_path(URL.from_text(u'/'))],
            AllMatch(Equals(u'/')))

    def test_unrooted_empty(self):
        """
        Unrooted empty path.
        """
        self.assertThat(
            url_path(URL.from_text(u'')),
            Equals(u''))

    def test_rooted(self):
        """
        Rooted path.
        """
        self.assertThat(
            [url_path(URL.from_text(u'http://example.com/foo/bar')),
             url_path(URL.from_text(u'/foo/bar'))],
            AllMatch(Equals(u'/foo/bar')))

    def test_unrooted(self):
        """
        Unrooted path.
        """
        self.assertThat(
            url_path(URL.from_text(u'foo/bar')),
            Equals(u'foo/bar'))


class ConstantlyTests(TestCase):
    """
    Tests for `constantly`.
    """
    def test_constantly(self):
        """
        Return the initial constant value regardless of any arguments passed.
        """
        f = constantly(42)
        self.assertThat(
            [f(),
             f(1),
             f(1, 2),
             f(1, b=2)],
            AllMatch(Equals(42)))
