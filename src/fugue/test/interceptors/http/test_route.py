from io import BytesIO

from hyperlink import URL
from pyrsistent import m, v
from testtools import ExpectedException, TestCase
from testtools.matchers import AfterPreprocessing as After
from testtools.matchers import (
    Contains, ContainsDict, Equals, Is, IsInstance, MatchesAll,
    MatchesListwise, MatchesStructure, Not)
from testtools.twistedsupport import succeeded

from fugue._keys import REQUEST, RESPONSE, ROUTE
from fugue.chain import execute
from fugue.interceptors.basic import Interceptor
from fugue.interceptors.http import route
from fugue.test.test_chain import empty_context, Traced, tracer
from fugue.util import url_path


def EnterStage(matcher, context=empty_context):
    """
    """
    return MatchesAll(
        IsInstance(Interceptor),
        After(lambda interceptor: interceptor.enter(context),
              matcher))


class RouteTests(TestCase):
    """
    Tests for `route.route`.
    """
    def test_utf8(self):
        """
        Byte paths are decoded as UTF-8, as a convenience.
        """
        interceptor = tracer('a')
        path = u'/\N{SNOWMAN}'
        self.assertThat(
            route.route(path.encode('utf-8'), route.GET, interceptor),
            MatchesStructure(path=Equals(path)))

    def test_no_interceptors(self):
        """
        Routes with no interceptors raise `ValueError`.
        """
        matcher = MatchesStructure(
            args=MatchesListwise([
                Equals('No interceptors specified')]))
        with ExpectedException(ValueError, matcher):
            route.route(u'foo', route.GET, [])

    def test_nested_interceptors(self):
        """
        Routes with nested interceptors raise `TypeError`.
        """
        matcher = MatchesStructure(
            args=MatchesListwise([
                Equals('Interceptors must not be nested'),
                Equals([])]))
        with ExpectedException(TypeError, matcher):
            route.route(u'foo', route.GET, [[]])

    def test_unknown_interceptor_type(self):
        """
        Routes with interceptor values that cannot be adapted raise
        `TypeError`.
        """
        matcher = MatchesStructure(
            args=MatchesListwise([
                Equals('Cannot be adapted to an interceptor'),
                Equals(42)]))
        with ExpectedException(TypeError, matcher):
            route.route(u'foo', route.GET, [42])

    def test_unrooted(self):
        """
        Routes with paths that are not rooted raise `ValueError`.
        """
        matcher = MatchesStructure(
            args=MatchesListwise([
                Equals('Route must be a rooted path'),
                Equals(URL.from_text(u'foo'))]))
        with ExpectedException(ValueError, matcher):
            route.route(u'foo', route.GET, [tracer('a')])

    def test_bare_interceptor(self):
        """
        Bare interceptors are placed into a pvector. The interceptor name
        becomes the route name.
        """
        interceptor = tracer('a')
        self.assertThat(
            route.route(u'/foo', route.GET, interceptor),
            MatchesStructure(
                name=Equals(interceptor.name),
                interceptors=Equals(v(interceptor))))

    def test_bare_callable(self):
        """
        Bare callables are wrapped in a `handler` interceptor and placed into a
        pvector. The function name becomes the route name.
        """
        def func(_):
            return 42
        self.assertThat(
            route.route(u'/foo', route.GET, func),
            MatchesStructure(
                name=Equals('func'),
                interceptors=MatchesListwise([
                    EnterStage(ContainsDict({RESPONSE: Equals(42)}))])))

    def test_iterable_interceptors(self):
        """
        Iterables have each item processed and wrapped, if necessary. The last
        interceptor / function's name becomes the route name.
        """
        def func(_):
            return 42
        trace = tracer('a')
        self.assertThat(
            route.route(u'/foo', route.GET, [trace, func]),
            MatchesStructure(
                name=Equals('func'),
                interceptors=MatchesListwise([
                    Equals(trace),
                    EnterStage(ContainsDict({RESPONSE: Equals(42)}))])))

    def test_priority_weighting(self):
        """
        More specific routes have a higher priority.
        """
        r = lambda path: route.route(path, route.GET, lambda _: None)
        self.assertThat(r(u'/foo'), MatchesStructure(priority=Equals(1)))
        self.assertThat(r(u'/foo/bar'), MatchesStructure(priority=Equals(2)))
        self.assertThat(r(u'/foo/*as'), MatchesStructure(priority=Equals(3)))
        self.assertThat(r(u'/foo/:a'), MatchesStructure(priority=Equals(4)))


def basic_request(method=route.GET, body=b'', uri=b'http://example.com/'):
    """
    Construct a suitable ``REQUEST`` context value.
    """
    uri = URL.from_text(uri).to_uri()
    return m(
        body=BytesIO(body),
        request_method=method,
        content_type=u'text/plain',
        character_encoding=u'utf-8',
        headers=m(),
        scheme=uri.scheme,
        path_info=url_path(uri))


class LinearSearchRouterTests(TestCase):
    """
    Tests for `LinearSearchRouter`.
    """
    def test_match_request_method(self):
        """
        Match the request method.
        """
        router = route.LinearSearchRouter(v(
            route.route(u'/foo', route.GET, [tracer('a')])))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo')),
            Not(Is(None)))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo', method=route.POST)),
            Is(None))

    def test_match_request_method_any(self):
        """
        Any request method matches the ``ANY`` method.
        """
        router = route.LinearSearchRouter(v(
            route.route(u'/foo', route.ANY, [tracer('a')])))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo')),
            Not(Is(None)))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo', method=route.POST)),
            Not(Is(None)))

    def test_match_path_basic(self):
        """
        Match a basic path with no identifiers or wildcards.
        """
        router = route.LinearSearchRouter(v(
            route.route(u'/foo', route.GET, [tracer('a')])))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo')),
            Not(Is(None)))
        self.assertThat(
            router.find_route(basic_request(uri=u'/bar')),
            Is(None))

    def test_match_path_identifiers(self):
        """
        Match a path with identifiers. Identifier values are stored in
        ``path_params``.
        """
        router = route.LinearSearchRouter(v(
            route.route(u'/foo/:a/:b', route.GET, [tracer('a')])))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo/1/2')),
            MatchesStructure.byEquality(
                path_params=m(a=u'1', b=u'2')))

    def test_match_path_identifier_constraints(self):
        """
        Match a path with identifiers while honouring identifier constraints.
        """
        self.skipTest('Not implemented')

    def test_match_path_wildcard(self):
        """
        Match a path with wildcards.
        """
        router = route.LinearSearchRouter(v(
            route.route(u'/foo/*rest', route.GET, [tracer('a')])))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo/1/2/bar')),
            MatchesStructure.byEquality(
                path_params=m(rest=u'1/2/bar')))

    def test_match_path_mixed(self):
        """
        Match a path that mixes wildcards and identifiers.
        """
        router = route.LinearSearchRouter(v(
            route.route(u'/foo/:a/*rest', route.GET, [tracer('a')])))
        self.assertThat(
            router.find_route(basic_request(uri=u'/foo/1/2/bar')),
            MatchesStructure.byEquality(
                path_params=m(a=u'1', rest=u'2/bar')))



class RouterInterceptorTests(TestCase):
    """
    Tests for `router` interceptor.
    """
    def test_route_tuple(self):
        """
        Routes can be specified as tuples.
        """
        interceptor = route.router(
            (u'/foo', route.GET, [tracer('a')]))
        context = empty_context.set(
            REQUEST, basic_request(uri=u'/foo'))
        self.assertThat(
            execute(context, [interceptor]),
            succeeded(Traced(
                Equals(
                    v(('enter', 'a'),
                      ('leave', 'a'))))))

    def test_route_route(self):
        """
        Routes can be specified as instances of `Route`.
        """
        interceptor = route.router(
            route.route(u'/foo', route.GET, [tracer('a')]))
        context = empty_context.set(
            REQUEST, basic_request(uri=u'/foo'))
        self.assertThat(
            execute(context, [interceptor]),
            succeeded(Traced(
                Equals(
                    v(('enter', 'a'),
                      ('leave', 'a'))))))

    def test_route_unknown(self):
        """
        Routes not a tuple or `Route` raise `TypeError`.
        """
        matcher = MatchesStructure(
            args=Equals(('Cannot be adapted to a route', 42)))
        with ExpectedException(TypeError, matcher):
            route.router(42)

    def test_route_names_not_distinct(self):
        """
        Raise `ValueError` if route names are not unique.
        """
        a = route.route(u'/foo', route.GET, [tracer('a')], u'a')
        b = route.route(u'/bar', route.GET, [tracer('a')], u'a')
        matcher = MatchesStructure(
            args=MatchesListwise([
                Equals('Non-unique route names'),
                Equals((a, b))]))
        with ExpectedException(ValueError, matcher):
            route.router(a, b)

    def test_route_unmatched(self):
        """
        If no route matches the request path, no ``ROUTE`` value is set on the
        context, and no route interceptors are enqueued.
        """
        interceptor = route.router(
            route.route(u'/foo', route.GET, [tracer('a')]))
        context = empty_context.set(
            REQUEST, basic_request(uri=u'/bar'))
        self.assertThat(
            execute(context, [interceptor]),
            succeeded(
                MatchesAll(
                    Equals(context),
                    Not(Contains(ROUTE)))))

    def test_path_specificity(self):
        """
        Ensure that more specific routes have a higher priority than less
        specific routes.
        """
        interceptor = route.router(
            route.route(u'/bar', route.GET, [tracer('b')], u'b'),
            route.route(u'/bar/:id/*rest', route.GET, [tracer('d')], u'd'),
            route.route(u'/foo', route.GET, [tracer('a')], u'a'),
            route.route(u'/bar/:id', route.GET, [tracer('c')], u'c'))
        req = lambda uri: execute(
            empty_context.set(REQUEST, basic_request(uri=uri)),
            [interceptor])
        self.assertThat(
            req(u'/foo'),
            succeeded(Traced(
                Equals(
                    v(('enter', 'a'),
                      ('leave', 'a'))))))
        self.assertThat(
            req(u'/bar'),
            succeeded(Traced(
                Equals(
                    v(('enter', 'b'),
                      ('leave', 'b'))))))
        self.assertThat(
            req(u'/bar/1'),
            succeeded(Traced(
                Equals(
                    v(('enter', 'c'),
                      ('leave', 'c'))))))
        self.assertThat(
            req(u'/bar/1/pa/th'),
            succeeded(Traced(
                Equals(
                    v(('enter', 'd'),
                      ('leave', 'd'))))))
