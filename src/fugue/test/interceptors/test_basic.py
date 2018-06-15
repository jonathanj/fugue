from pyrsistent import v
from testtools import TestCase
from testtools.matchers import ContainsDict, Equals, Is
from testtools.twistedsupport import succeeded

from fugue._keys import REQUEST, RESPONSE
from fugue.chain import execute
from fugue.interceptors import (
    after, around, before, error_handler, handler, middleware,
    on_request, on_response)
from fugue.test.test_chain import empty_context, thrower, Traced, tracer, tracing


VALUE = 'value'


class BeforeTests(TestCase):
    """
    Tests for `before`.
    """
    def test_before(self):
        """
        Interceptor only has an enter function.
        """
        interceptors = [
            tracer('a'),
            before(tracing('enter', 'b')),
            tracer('c')]
        self.assertThat(
            execute(empty_context, interceptors),
            succeeded(Traced(
                Equals(
                    v(('enter', 'a'),
                      ('enter', 'b'),
                      ('enter', 'c'),
                      ('leave', 'c'),
                      ('leave', 'a'))))))


class AfterTests(TestCase):
    """
    Tests for `after`.
    """
    def test_after(self):
        """
        Interceptor only has a leave function.
        """
        interceptors = [
            tracer('a'),
            after(tracing('leave', 'b')),
            tracer('c')]
        self.assertThat(
            execute(empty_context, interceptors),
            succeeded(Traced(
                Equals(
                    v(('enter', 'a'),
                      ('enter', 'c'),
                      ('leave', 'c'),
                      ('leave', 'b'),
                      ('leave', 'a'))))))


class AroundTests(TestCase):
    """
    Tests for `around`.
    """
    def test_around(self):
        """
        Interceptor only has an enter and leave function.
        """
        interceptors = [
            tracer('a'),
            around(tracing('enter', 'b'),
                   tracing('leave', 'b')),
            tracer('c')]
        self.assertThat(
            execute(empty_context, interceptors),
            succeeded(Traced(
                Equals(
                    v(('enter', 'a'),
                      ('enter', 'b'),
                      ('enter', 'c'),
                      ('leave', 'c'),
                      ('leave', 'b'),
                      ('leave', 'a'))))))


class ErrorHandlerTests(TestCase):
    """
    Tests for `error_handler`.
    """
    def test_error_handler(self):
        """
        Interceptor only has an error function.
        """
        def _swallow(marker):
            return lambda context, error: tracing(
                'error', (marker, 'from', error.failure.value.source))(context)
        interceptors = [
            tracer('a'),
            error_handler(_swallow('b')),
            thrower('c'),
            tracer('d')]
        self.assertThat(
            execute(empty_context, interceptors),
            succeeded(Traced(
                Equals(
                    v(('enter', 'a'),
                      ('error', ('b', 'from', 'c')),
                      ('leave', 'a'))))))


class HandlerTests(TestCase):
    """
    Tests for `handler`.
    """
    def test_handler(self):
        """
        """
        interceptors = [
            handler(lambda x: x)]
        value = object()
        context = empty_context.set(REQUEST, value)
        self.assertThat(
            execute(context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: Is(value),
                    RESPONSE: Is(value)})))


class MiddlewareTests(TestCase):
    """
    Tests for `middleware`.
    """
    context = empty_context.set(REQUEST, 42).set(RESPONSE, 21)

    def test_middleware(self):
        """
        Apply a function to the `REQUEST` value on enter and another function
        to the `RESPONSE` value on leave.
        """
        interceptors = [
            middleware(
                lambda req: ('enter', req),
                lambda res: ('leave', res))]
        self.assertThat(
            execute(self.context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: Equals(('enter', 42)),
                    RESPONSE: Equals(('leave', 21))})))

    def test_only_enter(self):
        """
        If the second function is ``None`` then do nothing in the leave stage.
        """
        interceptors = [
            middleware(
                lambda req: ('enter', req),
                None)]
        self.assertThat(
            execute(self.context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: Equals(('enter', 42)),
                    RESPONSE: Equals(21)})))

    def test_only_leave(self):
        """
        If the first function is ``None`` then do nothing in the enter stage.
        """
        interceptors = [
            middleware(
                None,
                lambda res: ('leave', res))]
        self.assertThat(
            execute(self.context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: Equals(42),
                    RESPONSE: Equals(('leave', 21))})))


class OnRequestTests(TestCase):
    """
    Tests for `on_request`.
    """
    context = empty_context.set(REQUEST, 42).set(RESPONSE, 21)

    def test_on_request(self):
        """
        Update the request.
        """
        interceptors = [
            on_request(lambda req: ('enter', req))]
        self.assertThat(
            execute(self.context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: Equals(('enter', 42)),
                    RESPONSE: Equals(21)})))


class OnResponseTests(TestCase):
    """
    Tests for `on_response`.
    """
    context = empty_context.set(REQUEST, 42).set(RESPONSE, 21)

    def test_on_response(self):
        """
        Update the response.
        """
        interceptors = [
            on_response(lambda res: ('leave', res))]
        self.assertThat(
            execute(self.context, interceptors),
            succeeded(
                ContainsDict({
                    REQUEST: Equals(42),
                    RESPONSE: Equals(('leave', 21))})))
