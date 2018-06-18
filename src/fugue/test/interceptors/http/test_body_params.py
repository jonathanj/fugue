import hashlib
import json
import urllib
from io import BytesIO

from pyrsistent import freeze, m, pmap
from testtools import TestCase
from testtools.matchers import AfterPreprocessing as After
from testtools.matchers import Always, ContainsDict, Equals, Is, MatchesDict
from testtools.twistedsupport import succeeded

from fugue._keys import REQUEST
from fugue.chain import execute
from fugue.interceptors.http import body_params
from fugue.interceptors.http.body_params import default_parsers
from fugue.test.test_chain import empty_context


class BodyParamsTests(TestCase):
    """
    Tests for `body_params`.
    """
    def payload(self):
        """
        Test payload.
        """
        return u'Hello world.'

    def request(self):
        """
        Construct the request map, including the payload.
        """
        return m(
            content_type='application/text; charset="utf-8"',
            character_encoding='utf-8',
            body=BytesIO(self.payload().encode('utf-8')))

    def test_unhandled(self):
        """
        If nothing can handle the content type, return the request untouched.
        """
        interceptors = [
            body_params()]
        context = empty_context.set(REQUEST, self.request())
        self.assertThat(
            execute(context, interceptors),
            succeeded(Equals(context)))


class JSONBodyParamsTests(TestCase):
    """
    Tests for the ``application/json`` aspect of `body_params`.
    """
    def payload(self):
        """
        Test payload.
        """
        return {
            u'a': 1,
            u'b': [2, 3],
            u'c': {u'd': u'\N{SNOWMAN}'},
            u'e': True}

    def request(self):
        """
        Construct the request map, including the payload.
        """
        def _json_dump(*a, **kw):
            return json.dumps(*a, **kw).encode('utf-8')
        return m(
            content_type='application/json; charset="utf-8"',
            character_encoding='utf-8',
            body=BytesIO(_json_dump(self.payload())))

    def test_default(self):
        """
        Default content parsers.
        """
        interceptors = [
            body_params()]
        context = empty_context.set(REQUEST, self.request())
        self.assertThat(
            execute(context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: ContainsDict({
                        'json_params': Equals(freeze(self.payload()))})})))

    def test_custom(self):
        """
        Custom content parsers.
        """
        interceptors = [
            body_params(default_parsers(json_options=dict(
                object_hook=lambda _: 42)))]
        context = empty_context.set(REQUEST, self.request())
        self.assertThat(
            execute(context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: ContainsDict({
                        'json_params': Equals(42)})})))


class FormBodyParamsTests(TestCase):
    """
    Tests for the ``application/x-www-form-urlencoded`` aspect of `body_params`.
    """
    def test_default(self):
        """
        Default content parsers.
        """
        interceptors = [
            body_params()]
        request = m(
            content_type='application/x-www-form-urlencoded; charset="utf-8"',
            character_encoding='utf-8',
            body=BytesIO(
                urllib.urlencode([
                    (b'a', b'1'),
                    (b'b', b'2'),
                    (b'b', b'3'),
                    (b'c', u'\N{SNOWMAN}'.encode('utf-8')),
                    (b'd', b'')])))
        context = empty_context.set(REQUEST, request)
        self.assertThat(
            execute(context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: ContainsDict({
                        'form_params': Equals(
                            pmap({
                                u'a': u'1',
                                u'b': [u'2', u'3'],
                                u'c': u'\N{SNOWMAN}',
                                u'd': True}))})})))


def open_test_data(path):
    import os.path
    return open(os.path.join(os.path.dirname(__file__), path), 'rb')


def Multipart(content_length, name, headers, body,
              character_encoding=Equals('latin1'), filename=Is(None),
              content_type=Is(None)):
    """
    """
    return MatchesDict({
        u'content_type': content_type,
        u'content_length': content_length,
        u'name': name,
        u'character_encoding': character_encoding,
        u'filename': filename,
        u'headers': headers,
        u'body': After(lambda x: x.read(), body),
    })


class MultipartFormBodyParamsTests(TestCase):
    """
    Tests for the ``multipart/form-data`` aspect of `body_params`.
    """
    def test_default(self):
        """
        Default content parsers.
        """
        interceptors = [
            body_params()]
        request = m(
            content_type='multipart/form-data; boundary=---------------------------114772229410704779042051621609',
            body=open_test_data('data/multipart_request'))
        context = empty_context.set(REQUEST, request)
        self.assertThat(
            execute(context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: ContainsDict({
                        'multipart_params': MatchesDict({
                            u'name': Multipart(
                                content_length=Equals(8),
                                name=Equals(u'name'),
                                headers=MatchesDict({
                                    u'Content-Disposition': Equals(
                                        u'form-data; name="name"'),
                                }),
                                body=Equals(b'Some One')),
                            u'email': Multipart(
                                content_length=Equals(16),
                                name=Equals(u'email'),
                                headers=MatchesDict({
                                    u'Content-Disposition': Equals(
                                        u'form-data; name="email"'),
                                }),
                                body=Equals(b'user@example.com')),
                            u'avatar': Multipart(
                                content_length=Equals(869),
                                content_type=Equals(u'image/png'),
                                filename=Equals(u'smiley-cool.png'),
                                name=Equals(u'avatar'),
                                headers=MatchesDict({
                                    u'Content-Type': Equals(u'image/png'),
                                    u'Content-Disposition': Equals(
                                        u'form-data; name="avatar"; filename="smiley-cool.png"'),
                                }),
                                body=After(
                                    lambda x: hashlib.sha256(x).hexdigest(),
                                    Equals(b'25fbe073db80f71a13fb8e0a190a76c0fda494d18849fa6fa87ea5a0924baa07'))),
                            # XXX: This syntax isn't supported by the multipart
                            # parser, multiple things with the same name are
                            # overwritten.
                            u'attachments[]': Always(),
                        }),
                        'form_params': MatchesDict({
                            u'name': Equals(u'Some One'),
                            u'email': Equals(u'user@example.com')})})})))
