from pyrsistent import dq, m, v
from testtools import TestCase
from testtools.matchers import AfterPreprocessing as After
from testtools.matchers import (
    AllMatch, Contains, ContainsDict, Equals, Is, MatchesStructure, Not)
from testtools.twistedsupport import failed, has_no_result, succeeded
from twisted.internet.defer import fail
from twisted.internet.task import Clock, deferLater

from fugue.chain import (
    enqueue, execute, QUEUE, terminate, terminate_when, TERMINATORS)
from fugue.interceptors import around
from fugue.util import constantly


empty_context = m()


class EnqueueTests(TestCase):
    """
    Tests for `enqueue`.
    """
    def test_empty(self):
        """
        Enqueuing interceptors creates the queue if necessary.
        """
        context = empty_context
        self.assertThat(
            enqueue(context, [1, 2, 3]),
            ContainsDict({
                QUEUE: Equals(dq(1, 2, 3))}))

    def test_non_empty(self):
        """
        Enqueue interceptors to a non-empty queue.
        """
        context = enqueue(empty_context, [1, 2, 3])
        self.assertThat(
            enqueue(context, [4, 5, 6]),
            ContainsDict({
                QUEUE: Equals(dq(1, 2, 3, 4, 5, 6))}))


class TerminateTests(TestCase):
    """
    Tests for `terminate`.
    """
    def test_empty(self):
        """
        Terminating an empty context is a noop.
        """
        context = empty_context
        self.assertThat(
            terminate(context),
            Not(Contains(QUEUE)))

    def test_non_empty(self):
        """
        Termating a context flushes its queue.
        """
        context = enqueue(empty_context, [1, 2, 3])
        self.assertThat(
            terminate(context),
            Not(Contains(QUEUE)))


class TerminateWhenTests(TestCase):
    """
    Tests for `terminate_when`.
    """
    always = constantly(True)
    never = constantly(False)

    def test_empty(self):
        """
        Adding the first terminator creates the vector if necessary.
        """
        context = empty_context
        self.assertThat(
            terminate_when(context, self.always),
            ContainsDict({
                TERMINATORS: Equals(v(self.always))}))

    def test_non_empty(self):
        """
        Adding a non-first terminator.
        """
        context = terminate_when(empty_context, self.always)
        self.assertThat(
            terminate_when(context, self.never),
            ContainsDict({
                TERMINATORS: Equals(v(self.always,
                                      self.never))}))


class TracingError(RuntimeError):
    """
    An error with an attribute used to trace the source for testing.
    """
    def __init__(self, source):
        self.source = source
        RuntimeError.__init__(self, 'Error traced from', source)


TRACE = '__trace'


def tracing(stage, marker):
    """
    Trace factory.
    """
    return lambda context: context.transform(
        [TRACE],
        lambda xs: (xs or v()).append((stage, marker)))


def trace(context, stage, marker):
    """
    Add a new trace event to the context.
    """
    return tracing(stage, marker)(context)


def tracer(marker):
    """
    Tracing interceptor.
    """
    return around(
        lambda context: trace(context, 'enter', marker),
        lambda context: trace(context, 'leave', marker),
        'tracer')


def deferrer(marker, clock, delay):
    """
    Tracing interceptor that returns a delayed result.
    """
    return around(
        lambda context: deferLater(
            clock, delay, lambda: trace(context, 'enter', marker)),
        lambda context: trace(context, 'leave', marker))


def thrower(marker):  # pragma: no cover
    """
    Tracing interceptor that raises an asynchronous exception.
    """
    return around(
        lambda context: fail(TracingError(marker)),
        lambda context: trace(context, 'leave', marker),
        'thrower')


def thrower_sync(marker):  # pragma: no cover
    """
    Tracing interceptor that raises a synchronous exception.
    """
    def _enter(context):
        raise TracingError(marker)
    return around(
        _enter,
        lambda context: trace(context, 'leave', marker),
        'thrower_sync')


def catcher(marker):  # pragma: no cover
    """
    Tracing interceptor that catches `TracingError`.
    """
    def _error(context, error):
        error.failure.trap(TracingError)
        return context.transform(
            [TRACE],
            lambda xs: (xs or v()).append(('error',
                                           marker,
                                           'from',
                                           error.failure.value.source)))
    return tracer(marker).set('error', _error)


def fumbling_catcher(marker):  # pragma: no cover
    """
    Tracing interceptor that fails to handle an error.
    """
    def _error(context, error):
        return fail(TracingError(marker))
    return tracer(marker).set('error', _error)


def Traced(matcher):
    """
    """
    return ContainsDict({TRACE: matcher})


class ExecuteTests(TestCase):
    """
    Tests for `execute`.
    """
    def test_simple(self):
        """
        Invoke interceptor "enter" events then "leave" events in reverse.
        """
        interceptors = [
            tracer('a'),
            tracer('b'),
            tracer('c')]
        self.assertThat(
            [execute(enqueue(empty_context, interceptors)),
             execute(empty_context, interceptors)],
            AllMatch(
                succeeded(Equals({
                    TRACE: v(('enter', 'a'),
                             ('enter', 'b'),
                             ('enter', 'c'),
                             ('leave', 'c'),
                             ('leave', 'b'),
                             ('leave', 'a'))}))))

    def test_async_error_propagates(self):
        """
        If an unhandled asynchronous error occurs in an interceptor it
        propogates along the execution.
        """
        interceptors = [
            tracer('a'),
            tracer('b'),
            thrower('c'),
            tracer('d')]
        self.assertThat(
            execute(empty_context, interceptors),
            failed(After(lambda f: f.type, Is(TracingError))))

    def test_sync_error_propagates(self):
        """
        If an unhandled synchronous error occurs in an interceptor it
        propogates along the execution.
        """
        interceptors = [
            tracer('a'),
            tracer('b'),
            thrower_sync('c'),
            tracer('d')]
        self.assertThat(
            execute(empty_context, interceptors),
            failed(After(lambda f: f.type, Is(TracingError))))

    def test_error_caught(self):
        """
        Interceptors can define an "error" stage that is capable of receiving
        and handling propagating errors.
        """
        interceptors = [
            tracer('a'),
            tracer('b'),
            catcher('c'),
            tracer('d'),
            tracer('e'),
            thrower('f'),
            tracer('g')]
        self.assertThat(
            execute(empty_context, interceptors),
            succeeded(
                Equals({
                    TRACE: v(('enter', 'a'),
                             ('enter', 'b'),
                             ('enter', 'c'),
                             ('enter', 'd'),
                             ('enter', 'e'),
                             ('error', 'c', 'from', 'f'),
                             ('leave', 'b'),
                             ('leave', 'a'))})))

    def test_error_fumble(self):
        """
        An interceptor that attempts but fails to handle an error, suppresses
        the original error and presents the new error.
        """
        interceptors = [
            tracer('a'),
            tracer('b'),
            fumbling_catcher('c'),
            tracer('d'),
            tracer('e'),
            thrower('f'),
            tracer('g')]
        self.assertThat(
            execute(empty_context, interceptors),
            failed(
                MatchesStructure(
                    type=Is(TracingError),
                    value=MatchesStructure(source=Equals('c')))))

    def test_deferred(self):
        """
        Any interceptor stage can return a `Deferred` and the execution will
        wait for it to resolve (or fail) before continuing.
        """
        clock = Clock()
        interceptors = [
            tracer('a'),
            deferrer('b', clock, 1),
            tracer('c')]
        d = execute(empty_context, interceptors)
        self.assertThat(d, has_no_result())
        clock.advance(1)
        self.assertThat(
            d,
            succeeded(
                Equals({
                    TRACE: v(('enter', 'a'),
                             ('enter', 'b'),
                             ('enter', 'c'),
                             ('leave', 'c'),
                             ('leave', 'b'),
                             ('leave', 'a'))})))

    def test_termination_predicate(self):
        """
        When a termination predicate is true, the "leave" phase is immediately
        entered.
        """
        interceptors = [
            tracer('a'),
            tracer('b'),
            tracer('c')]
        context = terminate_when(
            empty_context,
            lambda context: ('enter', 'b') in context.get(TRACE))
        self.assertThat(
            execute(context, interceptors),
            succeeded(
                ContainsDict({
                    TRACE: Equals(v(('enter', 'a'),
                                    ('enter', 'b'),
                                    ('leave', 'b'),
                                    ('leave', 'a')))})))
