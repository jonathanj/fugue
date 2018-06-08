=========================
Fugue: HTTP in two voices
=========================

.. image:: https://travis-ci.org/jonathanj/fugue.svg?branch=master
   :target: https://travis-ci.org/jonathanj/fugue
   :alt: CI status

.. image:: https://codecov.io/github/jonathanj/fugue/coverage.svg?branch=master
   :target: https://codecov.io/github/jonathanj/fugue?branch=master
   :alt: Coverage

.. teaser-begin

Fugue is a Python implementation of the *interceptor* concept as seen in, and
heavily inspired by, `Pedestal`_. It is currently built on `Twisted`_, the
event-driven networking engine for Python, and `Pyrsistent`_ for immutable data
structures.

Briefly, an interceptor is a reusable, composable component responsible for an
individual aspect of the overall behaviour of a web service, such as parsing a
query string or performing content negotiation. Combining interceptors produces
an execution chain that is easily expressed, understood and tested; logic is
kept small and isolated.

XXX: Link to docs, when they exist.

.. _Pedestal: http://pedestal.io/
.. _Twisted: https://twistedmatrix.com/
.. _Pyrsistent: https://github.com/tobgu/pyrsistent


------------
Interceptors
------------

Interceptors are the foundation of Fugue, and most of the library is dedicated
to providing interceptors that are useful for building HTTP services.

An interceptor is a pair of unary functions that accept a `context map`_—an
immutable data structure—and must eventually return a context map. One function,
``enter``, is called on the way "in" and another, ``leave``, is called on the
way "out". Either function may be omitted and the effect is that the context map
remains unchanged. The figure below demonstrates this for a single interceptor:

FIGURE 1

Interceptors are combined to produce a particular order of execution, the
"enter" stage is called in order for each interceptor with the—possibly
modified—context map flowing from one to the next. Once all interceptors have
been called, the "leave" stage is called in reverse order for each interceptor
threading the context map—resulting from the "enter" stage—through them;
illustrated below:

FIGURE 2

Asynchronous results, in the form of a Twisted `Deferred`_, may be returned from
any stage of an interceptor; the effect is that execution of the interceptor
chain is paused until the result becomes available.

Fugue keeps a queue of interceptors that have yet to be called in the context
map itself. Since interceptors are free to modify the context map, this means
they are also able to modify the remaining flow of execution! Terminating the
"enter" stage is a matter of clearing the queue, extending it is a matter of
enqueuing new interceptors; achieved by ``terminate`` and ``enqueue``
respectively.

.. _Deferred: https://twistedmatrix.com/documents/current/core/howto/defer.html


Example
^^^^^^^

A basic interceptor to attach a UUID to some ``uuid`` key on enter:

.. code-block:: python

   Interceptor(
       name='uuid',
       enter=lambda context: context.set(ns('uuid'), uuid4()))

Interceptors executing after this example would find a ``ns('uuid')`` key in the
context map containing a random UUID. In this case ``ns`` is some function
intended to produce namespaced keys to avoid collisions with either internal or
external keys. Fugue provides a basic function to help achieve this in the form
of ``namespace``.

A common pattern is to produce an interceptor from a function and capture the
arguments of the function (via a closure) within the interceptor's enter or
leave functions. For example attaching a database connection to each request:

.. code-block:: python

   def attach_database(uri):
       return Interceptor(
           name='db',
           enter=lambda context: context.set(ns('db'), connect_db(uri)))

XXX: MENTION ERROR HANDLING


-----------
Context map
-----------

XXX: DOCUMENT THIS


--------
Adapters
--------

Adapters are the mechanism that bind the external world (such as a web server)
to the internal world of interceptors. If interceptors consume and produce
immutable data via the context map then adapters transform some external
information—an HTTP request, for example—to and from that pure data.

Fugue provides a Twisted Web adapter in the form of an `IResource`_, the effect
of this adapter is to act as a leaf resource—meaning Twisted performs no child
resource lookups on it—that converts a Twisted Web request into a context map,
executes an interceptor chain, and converts the context map back into something
Twisted Web can respond to the request with.

An adapter has no formal structure since the coupling will depend on what is
being adapted.

.. _IResource: https://twistedmatrix.com/documents/current/api/twisted.web.resource.IResource.html


------------
Installation
------------

.. code-block:: shell

   pip install fugue


------------
Contributing
------------

See `CONTRIBUTING.rst`_.

.. _CONTRIBUTING.rst: https://github.com/jonathanj/fugue/blob/master/CONTRIBUTING.rst
