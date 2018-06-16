import collections
import re
import types

from hyperlink import URL
from pyrsistent import (
    field, freeze, inc, ny, pmap, pmap_field, PRecord, pvector_field, v)

from fugue._keys import REQUEST, ROUTE
from fugue.chain import enqueue
from fugue.interceptors.basic import handler, Interceptor
from fugue.util import callable_name, constantly, every_pred


_token_re = re.compile(ur'([*:])(.+)$')
regex_type = type(_token_re)


class _ParsedRoutePath(PRecord):
    """
    Parsed / derived components for matching a router path.
    """
    parts = pvector_field(unicode)
    params = pvector_field(unicode)
    constraints = pmap_field(unicode, unicode)
    priority = field(initial=0, type=int)


def _parse_path_segment(acc, segment):
    """
    Parse a single path segment.

    If the segment is an identifier or wildcard, it's constraint is also
    derived.

    :param _ParsedRoutePath acc: Accumulated parse result.
    :param unicode segment: Path segment.
    :rtype: _ParsedRoutePath
    """
    match = _token_re.match(segment)
    if match is not None:
        # XXX: Is it a problem that we're using strings for parameters and
        # strings for literal parts?
        t, token = match.groups()
        # Identifiers are more specific than wildcards.
        constraint, priority = (u'(.*)', 2) if t == u'*' else (u'([^/]+)', 3)
        return acc.transform(
            ['priority'], lambda x: x + priority,
            ['parts'], lambda x: x.append(token),
            ['params'], lambda x: x.append(token),
            ['constraints'], lambda x: x.set(token, constraint))
    else:
        return acc.transform(
            ['priority'], inc,
            ['parts'], lambda x: x.append(segment))


def _parse_path(path, parsed=_ParsedRoutePath()):
    """
    Parse a route path.

    :type path: Iterable[unicode]
    :param path: Route path segments.
    :param _ParsedRoutePath parsed: Partial parse result.
    :rtype: _ParsedRoutePath
    """
    return reduce(_parse_path_segment, path, parsed)


def _path_regex(path_parts, path_constraints):
    """
    Construct the regular expression to match a particular route path.

    :param pvector path_parts: ``path_parts`` component of a parsed route.
    :param pmap path_constraints: ``path_constrants`` component of a parsed
    route.
    :return: Compiled regular expression.
    """
    return re.compile(
        u'/' +
        u'/'.join(path_constraints.get(p, re.escape(p)) for p in path_parts))


class Route(PRecord):
    """
    Verbose route description.
    """
    name = field(mandatory=True, type=unicode)
    path = field(mandatory=True, type=unicode)
    method = field(mandatory=True, type=bytes)
    interceptors = pvector_field(Interceptor)

    path_re = field(mandatory=True, type=regex_type)
    path_parts = pvector_field(unicode)
    path_params = field(mandatory=True)
    path_constraints = pvector_field(unicode)
    #query_constraints = XXX

    priority = field(initial=0, type=int)
    matcher = field(mandatory=True, type=types.FunctionType)


# Convenience definitions for common methods.
GET = b'GET'
POST = b'POST'
PUT = b'PUT'
PATCH = b'PATCH'
DELETE = b'DELETE'
ANY = b'ANY'


def _conform_interceptor(interceptor, name, nesting=False):
    """
    Conform one or more things to interceptors.

    :param interceptor: `Interceptor`, ``callable`` or flat iterable of
    either to conform.
    :param unicode name: Potential route name, one will be derived if ``None``.
    :rtype: Tuple[pvector, unicode]
    :return: Pair of interceptors and a route name.
    """
    if isinstance(interceptor, Interceptor):
        return v(interceptor), name or interceptor.name
    elif callable(interceptor):
        name = name or callable_name(interceptor)
        return v(handler(interceptor, name=name)), name
    elif isinstance(interceptor, collections.Iterable):
        if nesting is True:
            raise TypeError('Interceptors must not be nested', interceptor)
        results = zip(
            *(_conform_interceptor(i, name, True) for i in interceptor))
        if not results:
            raise ValueError('No interceptors specified')
        interceptors, names = results
        return freeze([i[0] for i in interceptors]), names[-1]
    else:
        raise TypeError('Cannot be adapted to an interceptor', interceptor)


def route(path, method, interceptors, name=None):
    """
    Construct a route description.

    :param unicode path: Rooted route path to match, may include identifiers
    and wildcards (Rails-like syntax). For example: ``/users/:id/*rest``
    :param unicode method: Request method to match, with the special case of
    ``'ANY'`` to match any method.
    :type interceptors: Iterable[`Interceptor`]
    :param interceptors: Interceptors to enqueue when matching this route.
    :param unicode name: Route name, derived from the last interceptor's name
    if ``None``.
    :rtype: Route
    :return: Fully specified route to match.
    """
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    interceptors, name = _conform_interceptor(interceptors, name)
    if isinstance(name, bytes):
        name = name.decode('utf-8')
    iri = URL.from_text(path).to_iri()
    if not iri.rooted:
        raise ValueError('Route must be a rooted path', iri)
    parsed = _parse_path(iri.path)
    return Route(
        name=name,
        path=path,
        method=method,
        interceptors=interceptors,
        priority=parsed.priority,
        path_re=_path_regex(parsed.parts, parsed.constraints),
        path_parts=parsed.parts,
        path_params=parsed.params,
        path_constraints=parsed.constraints,
        matcher=constantly(None))


class LinearSearchRouter(object):
    """
    Router implementation that finds a route matching a request via a linear
    search.
    """
    def __init__(self, routes):
        """
        Construct the router.

        :type routes: pvector[`Route`]
        :param routes: Known routes.
        """
        self.routes = routes.transform(
            [ny],
            lambda r: r.set('matcher', self._route_matcher(r)))

    def find_route(self, request):
        """
        Find a `Route` that matches a request, or ``None``.
        """
        for route in self.routes:
            path_params = route.matcher(request)
            if path_params is not None:
                return route.set('path_params', path_params)

    @staticmethod
    def _route_matcher(route):
        """
        Create a route matching function.

        :param Route route: Route to build the matcher for.
        :return: Callable taking a ``REQUEST`` value from a context, returning
        ``None`` if no match or a pmap of matched path parameters.
        """
        def _base_matchers(route):
            method = route.method
            if method != ANY:
                yield lambda req: req['request_method'] == method

        def _path_matcher(route):
            def _path_matcher_inner(request):
                match = path_re.match(request['path_info'])
                if match:
                    return pmap(zip(path_params, match.groups()))
            path_re = route.path_re
            path_params = route.path_params
            return _path_matcher_inner

        base_match = every_pred(*_base_matchers(route))
        path_match = _path_matcher(route)
        return lambda req: (base_match(req) or None) and path_match(req)


def _enter_route(router, routes):
    """
    Enter stage for a router.

    Attempt to match the request to a known route and enqueue the matched
    route's interceptors if successful.
    """
    def _enter_route_inner(context):
        request = context[REQUEST]
        route = router.find_route(request)
        if route is None:
            return context.discard(ROUTE)
        context = context.transform(
            [ROUTE], route,
            [REQUEST], lambda req: req.set(
                'path_params', route['path_params']))
        return enqueue(context, route['interceptors'])
    return _enter_route_inner


def _conform_routes(routes):
    """
    Conform things that look like routes to `Route`.

    :param routes: Iterable of `Route` or ``tuple`` / ``list`` that will be
    applied to `route`. Route names must be unique.
    :rtype: Iterable[`Route`]
    :return: Conformed routes.
    """
    seen = {}
    for r in routes:
        if isinstance(r, (tuple, list)):
            r = route(*r)
        elif not isinstance(r, Route):
            raise TypeError('Cannot be adapted to a route', r)
        if r.name in seen:
            raise ValueError('Non-unique route names', (seen[r.name], r))
        seen[r.name] = r
        yield r


def _prioritize_routes(routes):
    """
    Reorder routes to ensure more specific routes have higher priority.
    """
    return freeze(sorted(routes, key=lambda r: r.priority, reverse=True))


def router_with(impl):
    """
    A factory that produces an interceptor with a given router implementation.

    .. seealso: `router`

    :param impl: A router implementation that is invoked with an iterable of
    `Route`\s.
    :rtype: Callable taking routes, returning an `Interceptor`.
    """
    def _router(*routes):
        routes = freeze(list(_prioritize_routes(_conform_routes(routes))))
        return Interceptor(
            name='router',
            enter=_enter_route(impl(routes), routes))
    return _router


def router(*routes):
    """
    An interceptor that matches incoming ``REQUEST`` context values against
    route criteria, enqueuing the interceptors for the matching route.

    The matching route is stored in the context at ``ROUTE`` and the path
    parameters at ``path_params`` in ``REQUEST``.

    :param *routes: Acceptable routes are either a `Route` instance (created
    via `route`) or a tuple of ``(path, method, interceptors, name)``,
    ``name`` may be omitted if a unique name can be derived from the
    interceptors. The two forms may be mixed.
    """
    return router_with(LinearSearchRouter)(*routes)


__all__ = [
    'Route', 'route', 'router_with', 'route', 'GET', 'POST', 'PUT', 'PATCH',
    'DELETE', 'ANY', 'LinearSearchRouter']
