import cgi
import json
from urlparse import parse_qs

import multipart
from pyrsistent import freeze, m, pmap

from fugue.util import identity, namespace
from fugue.interceptors.basic import on_request


_ns = namespace(__name__)


def _parser_for(parsers, content_type):
    """
    Find a parser for a particular content type.

    :param parsers: Mapping of content types to parsing functions.
    :param bytes content_type: Content type.
    :return: Callable to parse the content, falls back to the identity
    function.
    """
    for expr, parser in parsers.items():
        # XXX: Pedestal uses regexps instead of strings to match, why?
        if expr == content_type:
            return parser
    return identity


def _parse_content_type(parsers, request):
    """
    Parse the content of a request with the most suitable parser.

    :param parsers: Mapping of content types to parsing functions.
    :param request: Request map.
    :return: Updated request.
    """
    content_type, _ = cgi.parse_header(request['content_type'])
    return _parser_for(parsers, content_type)(request)


def json_parser(**kw):
    """
    Create a JSON parsing request processor.

    The parsed result will placed into a ``json_params`` key on the request.

    :param **kw: Additional keyword arguments to pass to `json.load`.
    :return: Request processor.
    """
    def _json_parser(request):
        encoding = request.get('character_encoding')
        return request.set(
            'json_params',
            freeze(json.load(
                request.body,
                encoding=encoding,
                **kw)))
    return _json_parser


def form_parser():
    """
    Create a form (``application/x-www-form-urlencoded``) parsing request
    processor.

    The parsed result will placed into a ``form_params`` key on the request.

    :param encoding: Request body encoding override, ``None`` will use the
    ``character_encoding`` value from the request and will fall back to UTF-8.
    :return: Request processor.
    """
    def _form_parser(request):
        encoding = request.get('character_encoding') or 'utf-8'
        _decode = lambda x: x.decode(encoding)
        _maybe_one = lambda x: x if len(x) > 1 else x[0] or True
        data = {_decode(k): _maybe_one(map(_decode, v)) for k, v
                in parse_qs(request.body.read(), True).items()}
        return request.set(
            'form_params',
            freeze(data))
    return _form_parser


def multipart_form_parser():
    """
    Create a multipart form (``multipart/form-data``) parsing request
    processor.

    The parsed result will placed into a ``multipart_params`` key on the request.
    Additionally, parts that are purely form data (``form-data`` disposition
    and no content type) will also be merged into a ``form_params`` key on the
    request.

    :return: Request processor.
    """
    def _multipart_form_parser(request):
        _, options = cgi.parse_header(request['content_type'])
        boundary = options['boundary']
        parser = multipart.MultipartParser(request.body, boundary)
        multipart_params = m().evolver()
        form_params = m().evolver()
        for part in parser.parts():
            if part.disposition == 'form-data' and not part.content_type:
                form_params[part.name] = part.value
            multipart_params[part.name] = m(
                content_type=part.content_type or None,
                content_length=part.size,
                headers=pmap(part.headerlist),
                name=part.name,
                filename=part.filename,
                character_encoding=part.charset,
                body=part.file)
        request = request.transform(
            ['form_params'],
            lambda params: params.update(form_params.persistent()))
        return request.set('multipart_params', multipart_params.persistent())
    return _multipart_form_parser


def default_parsers(json_options={}):
    """
    Default content type parsers.
    """
    return {
        b'application/json': json_parser(**json_options),
        b'application/x-www-form-urlencoded': form_parser(),
        b'multipart/form-data': multipart_form_parser(),
    }


def body_params(parsers=None):
    """
    An interceptor that attempts to parse parameters from a request body in the
    enter stage.

    Parsed information ends up in a specific key on the request, depending on
    which parser is used: ``json_params``, ``form_params``,
    ``multipart_params``, etc.

    :rtype: Interceptor.
    :return: Body-parsing interceptor.
    """
    if parsers is None:
        parsers = default_parsers()
    return on_request(
        lambda request: _parse_content_type(parsers, request),
        name=_ns('body_params'))


__all__ = ['body_params', 'default_parsers', 'json_parser', 'form_parser']
