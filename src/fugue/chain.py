import uuid

from pyrsistent import dq, field, PRecord, v
from twisted.internet.defer import maybeDeferred, succeed

from fugue._keys import ERROR, EXECUTION_ID, QUEUE, STACK, SUPPRESSED, TERMINATORS


class Error(PRecord):
    """
    An error that occured, in an interceptor, during context execution.
    """
    failure = field(mandatory=True)
    execution_id = field(mandatory=True)
    interceptor = field(type=(str, unicode))
    stage = field(mandatory=True, type=(str, unicode))


def enqueue(context, interceptors):
    """
    Add interceptors to the end of a context's execution queue.

    :param context: Context.
    :type interceptors: ``Iterable[`Interceptor`]``
    :param interceptors: Iterable of interceptors.
    :return: Updated context.
    """
    return context.transform(
        [QUEUE],
        lambda xs: (xs or dq()).extend(interceptors))


def terminate(context):
    """
    Remove all remaining interceptors from a context's execution queue. During
    execution this immediately ends the "enter" stage and begins the "leave" phase.

    :param context: Context.
    :return: Updated context.
    """
    return context.discard(QUEUE)


def terminate_when(context, pred):
    """
    Add a terminating condition for a context.

    These are evaluated at the end of each interceptor's "enter" function.

    :param context: Context.
    :param pred: Callable taking a context.
    :return: Updated context.
    """
    return context.transform(
        [TERMINATORS],
        lambda xs: (xs or v()).append(pred))


def _try_f(context, interceptor, stage):
    """
    Apply an interceptor handler for a particular stage, if it exists, on a
    context.

    Any errors (synchronous or asynchronous) are caught and attached to the
    context with the `ERROR` key.

    :param context: Context.
    :param interceptor: Interceptor.
    :param str stage: Executation phase.
    :return: Updated context.
    """
    def _eb(f, context):
        return context.set(
            ERROR,
            Error(failure=f,
                  execution_id=context[EXECUTION_ID],
                  interceptor=interceptor.name,
                  stage=stage))

    fn = getattr(interceptor, stage)
    if fn is None:
        return succeed(context)
    d = maybeDeferred(fn, context)
    d.addErrback(_eb, context)
    return d


def _try_error(context, interceptor):
    """
    Invoke an interceptor has an error stage, if it exists, on a context and
    the current `ERROR` from the context.

    :param context: Context.
    :param interceptor: Interceptor.
    :return: Updated context.
    """
    def _eb(f, context, error):
        # XXX: Hmm. Is this a useful check?
        if f.type is error.failure.type:
            return succeed(context)
        else:
            # XXX: Update the error with the new interceptor that tried to handle it?
            return succeed(
                context.transform(
                    [SUPPRESSED],
                    lambda xs: (xs or v()).append(f)))
    stage = 'error'
    fn = getattr(interceptor, stage, None)
    if fn is None:
        return succeed(context)
    error = context[ERROR]
    d = maybeDeferred(fn, context.discard(ERROR), error)
    d.addErrback(_eb, context, error)
    return d


def _next_uuid_str():
    """
    Random UUID expressed as a string.
    """
    return str(uuid.uuid4())


def _begin(context, next_id=_next_uuid_str):
    """
    Prepare a context for execution.

    :param context: Context.
    :type next_id: ``Callable[[], str]``
    :param next_id: Callable to produce a new execution identifier.
    :return: Updated context.
    """
    if EXECUTION_ID in context:
        return context
    execution_id = next_id()
    return context.set(EXECUTION_ID, execution_id)


def _check_terminators(context):
    """
    If any of the `TERMINATORS` predicates return True, terminate the
    execution.

    :param context: Context.
    :return: Updated context.
    """
    preds = context.get(TERMINATORS, v())
    if any(pred(context) for pred in preds):
        return context.discard(QUEUE)
    return context


def _enter_all(context):
    """
    Invoke the "enter" stage of each interceptor from `QUEUE` and saving the
    interceptors on `STACK`.

    If an error occurs, execution is terminated.

    :param context: Context.
    :return: Updated context.
    """
    def _check_error(context):
        if ERROR in context:
            return context.discard(QUEUE)
        return _check_terminators(context)

    def _enter(context):
        queue = context.get(QUEUE, dq())
        if not queue:
            return succeed(context)
        stack = context.get(STACK, dq())
        interceptor = queue.left
        new_queue = queue.popleft()
        new_stack = stack.appendleft(interceptor)
        d = _try_f(
            context.update({
                QUEUE: new_queue,
                STACK: new_stack}),
            interceptor, 'enter')
        d.addCallback(_check_error)
        d.addCallback(_enter)
        return d
    return _enter(context)


def _leave_all(context):
    """
    Invoke the "leave" stage of each interceptor from `STACK`.

    If an error occurred in the "enter" stage, each interceptor on the stack is
    given the opportunity to handle the error.

    :param context: Context.
    :return: Updated context.
    """
    def _leave(context):
        stack = context.get(STACK, dq())
        if not stack:
            return succeed(context)
        interceptor = stack.left
        context = context.transform([STACK], lambda s: s.popleft())
        if ERROR in context:
            d = _try_error(context, interceptor)
        else:
            d = _try_f(context, interceptor, 'leave')
        return d.addCallback(_leave)
    return _leave(context)


def _end(context):
    """
    Prepare a context for the end of execution.

    :param context: Context.
    :return: Updated context.
    """
    return context.discard(EXECUTION_ID).discard(STACK)


def execute(context, interceptors=None):
    """
    Execute a queue of interceptors attached to a context.

    When executing a context, first the ``enter`` functions of interceptors are
    invoked in order, and the executed interceptors added to a stack.

    When the execution reaches the end of the queue, either naturally or by way
    of a termination condition, the ``leave`` functions of interceptors on the
    stack are invoked, producing the effect of ``leave`` being executed in
    reverse order from ``enter``.

    If any interceptor raises an error (synchronous or asynchronous), the
    "enter" stage is immediately terminated and the "error" stage begins. Each
    executed interceptor is given the opportunity to handle the error. If the
    error is handled then the "leave" stage resumes from the next interceptor.
    If the error reaches the end of the "leave" stage without being handled it
    will be raised from `execute` as an asynchronous error.

    Any of the ``enter``, ``leave`` or ``error`` functions may return an
    asynchronous result and execution of the context will be paused until the
    result is delivered.

    :param context: Context.
    :type interceptors: ``Iterable[Interceptor]``
    :param interceptors: Interceptors to optionally enqueue.
    :rtype: Deferred
    :return: Resulting context.
    """
    def _maybe_error(context):
        error = context.get(ERROR)
        if error:
            return error.failure
        return context
    if interceptors is not None:
        context = enqueue(context, interceptors)
    d = _enter_all(_begin(context))
    d.addCallback(terminate)
    d.addCallback(_leave_all)
    d.addCallback(_end)
    d.addCallback(_maybe_error)
    return d


__all__ = ['enqueue', 'terminate', 'terminate_when', 'execute']
